"""Gateway app factory: the composition root (ADR 0005, ADR 0006, scope #28 /v1, #46).

Builds the adapters (case.db engine, SqlLedger, LangGraph SqliteSaver, LLM or none), injects
them into the Supervisor with the stage agents, and mounts the /v1 routers plus each agent's
router at /v1/agents/<name>. Agent routers reach the Supervisor only through the service.
"""

from __future__ import annotations

import dataclasses
import functools
import json
import logging
import os
import sqlite3
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from langgraph.checkpoint.sqlite import SqliteSaver
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter
from sqlalchemy import Engine

from credassure.agents.copilot.api import deps as copilot_deps
from credassure.agents.copilot.api.router import router as copilot_router
from credassure.agents.critic import agent as critic
from credassure.agents.critic.api import deps as critic_deps
from credassure.agents.critic.api.router import router as critic_router
from credassure.agents.critic.verify import Fact, Resolve, verify
from credassure.agents.lendwise import agent as lendwise
from credassure.agents.lendwise.api import deps as lendwise_deps
from credassure.agents.lendwise.api.router import router as lendwise_router
from credassure.agents.onboarding import agent as onboarding
from credassure.agents.onboarding.api import deps as onboarding_deps
from credassure.agents.onboarding.api.router import router as onboarding_router
from credassure.agents.supervisor.api import deps as supervisor_deps
from credassure.agents.supervisor.api.router import router as supervisor_router
from credassure.agents.supervisor.graph import Supervisor, default_rechecks
from credassure.agents.working_capital import agent as working_capital
from credassure.agents.working_capital.api import deps as working_capital_deps
from credassure.agents.working_capital.api.router import router as working_capital_router
from credassure.core import narrative
from credassure.core.enums import AgentName, Stage
from credassure.core.errors import ApiErrorCode
from credassure.core.findings import CriticFinding
from credassure.core.money import from_paise
from credassure.core.ports import LLMPort, ToolPort
from credassure.core.results import AgentResult
from credassure.engines import (
    affordability,
    calendar,
    cashflow,
    loancost,
    offer_audit,
    onboarding_rules,
    ranking,
)
from credassure.gateway import problems, tracing
from credassure.gateway.deps import Services, current_user
from credassure.gateway.jobs import JobRunner
from credassure.gateway.routers import admin, auth, cases, citations, health, lineage, workflow
from credassure.gateway.settings import Settings, get_settings
from credassure.gateway.supervisor_service import SupervisorService
from credassure.ledger import hr, migrate, reads
from credassure.ledger.session import case_engine, hr_engine, transaction
from credassure.ledger.store import SqlLedger
from credassure.lender_sim import ScriptedLender
from credassure.observability.log import configure_logging, log_context, set_redactor
from credassure.retrieval.search import Filters, Searcher, make_reranker, resolve
from credassure.security import pii
from credassure.security.auth import verify_token
from credassure.tools.registry import RegistryError, authorize_fact, is_display_only
from credassure.tools.runner import ToolRunner

_log = logging.getLogger("credassure.gateway")
_AGENT_ROUTERS = (
    ("supervisor", supervisor_router, supervisor_deps),
    ("onboarding", onboarding_router, onboarding_deps),
    ("working-capital", working_capital_router, working_capital_deps),
    ("lendwise", lendwise_router, lendwise_deps),
    ("critic", critic_router, critic_deps),
    ("copilot", copilot_router, copilot_deps),
)
_STAGE_AGENTS = {
    Stage.ONBOARDING: onboarding.run,
    Stage.WORKING_CAPITAL: working_capital.run,
    Stage.LENDWISE: lendwise.run,
    Stage.CRITIC: critic.run,
}


class _Clock:
    """AS_OF_DATE, never date.today(), so results reproduce (DATA_SPEC §1)."""

    def __init__(self, as_of: date) -> None:
        self.as_of = as_of

    def today(self) -> date:
        return self.as_of


def _default_llm(settings: Settings) -> LLMPort | None:
    if not settings.llm_enabled or not settings.llm_base_url:
        return None
    import ssl

    import httpx2

    from credassure.llm.cache import ResponseCache
    from credassure.llm.client import OpenAICompatLLM
    from credassure.llm.resilience import CircuitBreaker, configure_shared_limiter

    key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    ca = settings.llm_ca_cert
    return OpenAICompatLLM(
        settings.llm_base_url,
        key,
        settings.llm_model or "default",
        call_timeout=settings.llm_call_timeout_s,
        retries=settings.llm_max_retries,
        breaker=CircuitBreaker(settings.llm_circuit_failures, settings.llm_circuit_open_s),
        limiter=configure_shared_limiter(settings.llm_rate_per_minute),
        cache=ResponseCache(settings.llm_cache_path) if settings.llm_cache_path else None,
        guided_json=settings.llm_supports_guided_json,
        max_tokens=settings.llm_max_tokens,
        disable_thinking=settings.llm_disable_thinking,
        thinking_switch=settings.llm_thinking_switch,
        http_client=httpx2.Client(verify=ssl.create_default_context(cafile=ca)) if ca else None,
    )


def _profile_loader(settings: Settings, engine: Engine) -> Callable[[str], dict[str, Any] | None]:
    """Case -> its preparer's emp_id (login binding) -> hr.db profile (ONB-01, SUP-08)."""
    hr_db = hr_engine(settings.hr_db)

    def load(case_id: str) -> dict[str, Any] | None:
        with transaction(engine) as s:
            emp_id = reads.preparer_emp_id(s, settings.tenant_id, case_id)
        return None if emp_id is None else hr.load_profile(hr_db, emp_id)

    return load


def _case_inputs(settings: Settings, engine: Engine) -> Callable[[str], working_capital.CaseInputs]:
    """Case -> its latest stored file per kind and indicative request (read-only, SUP-08)."""

    def load(case_id: str) -> working_capital.CaseInputs:
        with transaction(engine) as s:
            case = reads.get_case(s, settings.tenant_id, case_id)
            rows = reads.case_files(s, settings.tenant_id, case_id)  # ascending id: newest wins
            stored = {r.kind: (r.sha256, json.loads(r.payload_json)) for r in rows}
        if case is None:
            raise LookupError("case not found")
        indicative = from_paise(case.indicative_amount_paise)
        return working_capital.load_inputs(stored, indicative, settings.forecast_weeks)

    return load


def _reference_rates(settings: Settings) -> tuple[lendwise.ReferenceRate, ...]:
    """S22 reference rates in force on AS_OF_DATE, each with its cited source (R-RATE-02).
    Values must be quoted strings (never float). Missing file: fatal outside tests."""
    path = settings.reference_rates_file
    if not path.is_file():
        if settings.app_env == "test":
            return ()
        raise RuntimeError(f"reference rates file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rates = []
    for r in data.get("rates", []):
        if not isinstance(r.get("value_pct"), str):
            raise ValueError(f"reference rate {r.get('id')}: value_pct must be a quoted string")
        if date.fromisoformat(str(r["effective_from"])) <= settings.as_of_date:
            rate = Decimal(r["value_pct"])
            rates.append(lendwise.ReferenceRate(str(r["id"]), rate, str(r["source_doc_id"])))
    return tuple(rates)


def _offer_inputs(settings: Settings, engine: Engine) -> Callable[[str], lendwise.Inputs]:
    """Case -> its uploaded offers and KFS schedules plus its funding position (read-only)."""
    funding, rates = _case_inputs(settings, engine), _reference_rates(settings)
    week1 = calendar.week1_start(settings.as_of_date)

    def load(case_id: str) -> lendwise.Inputs:
        with transaction(engine) as s:
            rows = reads.case_files(s, settings.tenant_id, case_id)  # ascending id
            uploads = [
                (r.kind, r.sha256, json.loads(r.payload_json))
                for r in rows
                if r.kind in ("offer", "kfs")
            ]
        wc = funding(case_id)
        position = (
            None
            if wc.blockers or wc.files is None
            else lendwise.position(wc.files, wc.indicative, wc.weeks, week1)
        )
        cls = str(wc.files.order.get("enterprise_class", "")) if wc.files else ""
        return lendwise.load_inputs(uploads, cls, position, rates)

    return load


@functools.cache
def _superseded_index(manifest: Path) -> dict[str, str | None]:
    """Manifest doc_id -> superseded_by, parsed once per process and only when a text cites."""
    if not manifest.exists():
        return {}
    data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    return {d["doc_id"]: d.get("superseded_by") for d in data.get("documents") or []}


def _filters(settings: Settings, engine: Engine, case_id: str, **kw: Any) -> Filters:
    """ADR 0019 filters for this case, plus the corpus KFS it uploaded itself (9e)."""
    with transaction(engine) as s:
        own = reads.own_kfs(s, settings.tenant_id, case_id)
    return Filters(as_of=settings.as_of_date, home_state=settings.home_state, own_kfs=own, **kw)


def _resolver(settings: Settings, engine: Engine) -> Callable[[str], Resolve | None]:
    """VER-02: a per-case citation resolver over the indexed corpus (None before `make ingest`;
    the Critic then fails any citation closed)."""

    def for_case(case_id: str) -> Resolve | None:
        if not settings.corpus_db.exists():
            return None
        filters = _filters(settings, engine, case_id)
        return lambda ids: resolve(
            settings.corpus_db,
            ids,
            case_id=case_id,
            tenant_id=settings.tenant_id,
            filters=filters,
            known=_superseded_index(settings.corpus_manifest),
        )

    return for_case


def _facts(settings: Settings, engine: Engine, case_id: str) -> dict[str, Fact]:
    with transaction(engine) as s:
        rows = reads.list_for_case(s, settings.tenant_id, case_id)  # key, version order
    # the last version wins; display-only text (the lender's reply) never counts as a figure
    return {f.key: Fact(f.value_text, f.unit) for f in rows if not is_display_only(f.key)}


def _verify_claims(settings: Settings, engine: Engine) -> Callable[..., list[CriticFinding]]:
    """The Critic's verify_claims tool (VER-01..03): figures against this case's ledger, reasons
    against code slots, citations against the corpus, banned wording and PII. A2: switched off."""
    resolver = _resolver(settings, engine)

    def verify_claims(
        case_id: str,
        text: str,
        slots: dict[str, str] | None = None,
        model: bool = False,
        stage: str | None = None,
        keys: list[str] | None = None,
    ) -> list[CriticFinding]:
        """``keys``: the only facts the text may quote (all of the case's facts when omitted)."""
        if settings.ablation == "A2":
            return []
        facts = _facts(settings, engine, case_id)
        if keys is not None:
            facts = {k: v for k, v in facts.items() if k in keys}
        return verify(
            text,
            facts=facts,
            slots=slots,
            model=model,
            stage=Stage(stage) if stage else None,
            resolve=resolver(case_id),
        )

    return verify_claims


_NARRATIVE_PREFIX = {Stage.ONBOARDING: "onb.", Stage.WORKING_CAPITAL: "wc.", Stage.LENDWISE: "lw."}


def _stage_critic(
    settings: Settings, engine: Engine
) -> Callable[[AgentResult], list[CriticFinding]]:
    """VER-05: the Supervisor's check of each stage narrative, with the slots it was recorded
    with. A narrative stage whose text has no matching record fails closed: judged as model text
    with no slots. Stages without a narrative record (critic) are code text."""
    verify_claims = _verify_claims(settings, engine)

    def check(result: AgentResult) -> list[CriticFinding]:
        text = result.narrative or ""
        prefix = _NARRATIVE_PREFIX.get(result.stage)
        stored = None
        if prefix is not None:
            with transaction(engine) as s:
                fact = reads.get_latest(s, settings.tenant_id, result.case_id, prefix + "narrative")
            stored = narrative.parse(fact.value_text if fact else None)
        slots: dict[str, str] = {}
        model = prefix is not None  # fail closed for a narrative stage without its record
        if stored is not None and stored[0] == pii.redact(text):  # records are stored redacted
            _, model, slots = stored
        return verify_claims(result.case_id, text, slots, model, result.stage.value)

    return check


def _lendwise_handlers(settings: Settings, engine: Engine) -> dict[str, Callable[..., Any]]:
    """LW engines as tools. Pure calls; only load_offers reads the case (SUP-08)."""
    load = _offer_inputs(settings, engine)
    gst, convention = settings.gst_rate, settings.apr_convention
    lender = ScriptedLender(settings.lender_scripts_dir)

    def price(case_id: str, offers: list[dict[str, Any]], hidden: dict[str, Any]) -> Any:
        return {
            o["offer_id"]: (
                loancost.price(
                    o, hidden.get(o["offer_id"], ()), gst_rate=gst, convention=convention
                ),
                loancost.gst_total(o, hidden.get(o["offer_id"], ()), gst_rate=gst),
            )
            for o in offers
        }

    def afford(
        case_id: str, position: lendwise.Position, offers: list[dict[str, Any]], flows: Any
    ) -> Any:
        return {
            o["offer_id"]: affordability.assess(
                position.cumulative,
                position.available,
                position.buffer,
                flows[o["offer_id"]],
                date.fromisoformat(str(o["disbursal_date"])),
                position.week1,
                Decimal(str(o["principal"])),
                position.need,
                position.peak_week,
            )
            for o in offers
        }

    return {
        "load_offers": lambda case_id: load(case_id),
        "audit_offer": lambda case_id, offers, hidden, unpriced, enterprise_class: {
            o["offer_id"]: offer_audit.audit(
                o,
                hidden.get(o["offer_id"], ()),
                enterprise_class,
                unpriced.get(o["offer_id"], ()),
            )
            for o in offers
        },
        "price_offer": price,
        "check_affordability": afford,
        "rank_offers": lambda case_id, candidates, need: ranking.rank(candidates, need),
        "verify_claims": _verify_claims(settings, engine),
        # scope: simulated lender only; the tool sends a request and returns its reply (LW-13)
        # stateless: it receives only this case's target offer and schedule (SUP-08)
        "lender_send_template": lambda case_id, **kw: lender.send(**kw),
    }


def _offer_preview(settings: Settings, engine: Engine) -> Callable[[str], dict[str, str]]:
    """LW-02..08 audit and pricing without affordability or ranking, for a case whose funding
    stage is not GO (SUP-03 keeps the stage from running). Writes nothing."""
    load, handlers = _offer_inputs(settings, engine), _lendwise_handlers(settings, engine)

    def preview(case_id: str) -> dict[str, str]:
        inputs = load(case_id)
        if not inputs.offers:
            return {}
        inputs = lendwise.Inputs(inputs.offers, inputs.schedules, inputs.enterprise_class, None)
        hidden = lendwise.code_hidden(inputs) if lendwise.ready(inputs) else {}
        c = lendwise.compare(ToolRunner(AgentName.LENDWISE, handlers), case_id, inputs, hidden)
        return {k: str(v) for k, (v, _) in lendwise.facts_for(c, inputs).items()}

    return preview


def _searcher(settings: Settings) -> Callable[[], Searcher]:
    """Built on first use (the embedder and reranker load models). Same store and embedder as
    `make ingest`; keyword mode needs neither."""

    @functools.cache
    def build() -> Searcher:
        reranker = make_reranker(
            settings.reranker, settings.reranker_model, settings.reranker_revision
        )
        rewrite, gate = settings.retrieval_query_rewrite, settings.answerability_threshold
        order = settings.rerank_order
        if settings.copilot_search_mode == "keyword":
            return Searcher(
                settings.corpus_db, None, None, reranker=reranker, query_rewrite=rewrite,
                min_score=gate, rerank_order=order,
            )  # fmt: skip
        from credassure.retrieval.cli import embedder
        from credassure.retrieval.index import open_chroma

        return Searcher(
            settings.corpus_db,
            open_chroma(settings.chroma_path),
            embedder(os.environ),
            reranker=reranker,
            tenant_id=settings.tenant_id,
            query_rewrite=rewrite,
            min_score=gate,
            rerank_order=order,
        )

    return build


def _copilot_handlers(settings: Settings, engine: Engine) -> dict[str, Callable[..., Any]]:
    """The copilot's four fixed tools (scope #20) plus the Critic. case_id is injected by the
    tool runner (SUP-08); collections and filters are fixed here, never chosen by the model."""
    searcher = _searcher(settings)

    def search(collections: tuple[str, ...]) -> Callable[..., list[dict[str, Any]]]:
        def run(case_id: str, query: str) -> list[dict[str, Any]]:
            if not settings.corpus_db.exists():
                return []
            hits = searcher().search_knowledge(
                query,
                case_id=case_id,
                tenant_id=settings.tenant_id,
                filters=_filters(settings, engine, case_id, collections=collections),
                mode=settings.copilot_search_mode,
                k=5,
            )
            return [
                {
                    **dataclasses.asdict(p),
                    "effective_from": p.effective_from.isoformat() if p.effective_from else None,
                }
                for p in hits
            ]

        return run

    def case_facts(case_id: str) -> dict[str, dict[str, str]]:
        out = {}
        for key, fact in _facts(settings, engine, case_id).items():
            try:
                authorize_fact(AgentName.COPILOT, key)  # registry read prefixes (#24)
            except RegistryError:
                continue
            out[key] = {"value": fact.value, "unit": fact.unit}
        return out

    def explain_blocker(case_id: str) -> dict[str, Any]:
        with transaction(engine) as s:
            runs = reads.stage_runs(s, settings.tenant_id, case_id)
        latest = {r.stage: r for r in runs}  # attempts ascend
        blocked = [
            AgentResult.model_validate_json(r.result_json)
            for r in latest.values()
            if r.result_json and r.decision not in ("GO", None)
        ]
        return {
            "question": next((b.question for b in blocked if b.question), None),
            "blockers": [b.model_dump(mode="json") for res in blocked for b in res.blockers],
        }

    return {
        "search_regulations": search(("public",)),
        "search_policies": search(("policy", "kfs")),
        "get_case_facts": case_facts,
        "explain_blocker": explain_blocker,
        "verify_claims": _verify_claims(settings, engine),
    }


def _tool_factory(settings: Settings, engine: Engine) -> Callable[[AgentName], ToolPort]:
    load = _profile_loader(settings, engine)
    inputs = _case_inputs(settings, engine)
    handlers: dict[AgentName, dict[str, Callable[..., Any]]] = {
        AgentName.ONBOARDING: {  # read-only: no tool writes HR data (ONB-05)
            "get_hr_profile": lambda case_id: load(case_id),
            "evaluate_onboarding_rules": lambda case_id, profile: onboarding_rules.evaluate(
                profile, settings.as_of_date
            ),
        },
        AgentName.WORKING_CAPITAL: {  # case files are read here only; no tool writes them
            "validate_case_files": lambda case_id: inputs(case_id),
            "compute_cash_table": lambda case_id, files, weeks: cashflow.cash_table(files, weeks),
            "compute_recommendation": lambda case_id, files, table, indicative: cashflow.recommend(
                files, table, indicative=indicative
            ),
        },
        AgentName.LENDWISE: _lendwise_handlers(settings, engine),  # no tool accepts an offer
        AgentName.CRITIC: {"verify_claims": _verify_claims(settings, engine)},  # VER-01..03
        AgentName.COPILOT: _copilot_handlers(settings, engine),  # 9e, on demand via chat
    }

    def tools(agent: AgentName) -> ToolPort:
        return ToolRunner(agent, handlers.get(agent, {}))

    return tools


def build_services(settings: Settings, llm: LLMPort | None) -> Services:
    migrate.upgrade("case", settings.case_db)  # idempotent; seeds stay separate (#29)
    engine = case_engine(settings.case_db)
    ledger = SqlLedger(engine, settings.tenant_id)
    rechecks = {  # SUP-05: the stage's own recomputation; other stages keep the default
        Stage.ONBOARDING: onboarding.make_recheck(
            _profile_loader(settings, engine), settings.as_of_date
        ),
        Stage.WORKING_CAPITAL: working_capital.make_recheck(_case_inputs(settings, engine)),
        Stage.LENDWISE: lendwise.make_recheck(
            lambda: ToolRunner(AgentName.LENDWISE, _lendwise_handlers(settings, engine)),
            _offer_inputs(settings, engine),
        ),
    }
    with transaction(engine) as s:
        rule = reads.get_config(s, settings.tenant_id, "boundary_rule") or settings.boundary_rule
    saver = SqliteSaver(sqlite3.connect(settings.case_db, check_same_thread=False))
    supervisor = Supervisor(
        agents=_STAGE_AGENTS,
        store=ledger,
        ledger=ledger,
        tools=_tool_factory(settings, engine),
        rechecks={**default_rechecks(), **rechecks},
        llm=llm if settings.llm_enabled else None,
        clock=_Clock(settings.as_of_date),
        checkpointer=saver,
        tenant_id=settings.tenant_id,
        max_steps=settings.agent_max_steps,
        token_cap=settings.token_cap_per_stage,
        stage_timeout=settings.stage_timeout_s,
        planner_mode=settings.planner_mode,
        ablation=settings.ablation,
        boundary_rule=rule,  # type: ignore[arg-type]  # validated on write (admin) and in settings
        critic=_stage_critic(settings, engine),
    )
    svc = Services(
        settings=settings,
        engine=engine,
        ledger=ledger,
        supervisor=supervisor,
        llm=supervisor.llm,
        jobs=JobRunner(engine, ledger, supervisor),
    )
    svc.service = SupervisorService(svc)
    svc.offer_preview = _offer_preview(settings, engine)
    svc.verify_claims = _verify_claims(settings, engine)
    tools = _tool_factory(settings, engine)
    svc.copilot_tools = lambda: tools(AgentName.COPILOT)  # a fresh runner per chat turn
    return svc


def _rate_key(settings: Settings, request: Request) -> str:
    """Per user (signature-verified JWT sub), else per client IP (NFR-04).

    No DB read here: an invalid or forged token simply shares its client IP's bucket.
    """
    header = request.headers.get("authorization", "")
    secret = settings.jwt_secret
    if secret is not None and header.lower().startswith("bearer "):
        try:
            return "user:" + verify_token(header[7:], secret.get_secret_value()).user_id
        except Exception:  # any bad token falls back to the IP bucket
            _log.debug("rate-limit key: token rejected, using client IP")
    return "ip:" + (request.client.host if request.client else "unknown")


def create_app(settings: Settings | None = None, *, llm: LLMPort | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    set_redactor(pii.redact)  # NFR-07: Verhoeff-aware redaction for every log line
    tracing.configure(settings)
    svc = build_services(settings, llm if llm is not None else _default_llm(settings))
    app = FastAPI(title="CredAssure API", version="0.2.0")
    app.state.settings = settings
    app.state.services = svc
    problems.install(app)
    # ponytail: in-memory buckets per process; use limits' Redis storage if the gateway scales out.
    limiter, rate = MovingWindowRateLimiter(MemoryStorage()), parse(settings.rate_limit)
    app.state.login_limiter = MovingWindowRateLimiter(MemoryStorage())  # S4, routers/auth.py

    @app.middleware("http")
    async def rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.startswith("/v1/health/") or limiter.hit(
            rate, _rate_key(settings, request)
        ):
            return await call_next(request)
        return problems.problem_response(
            request, 429, "rate limit exceeded", ApiErrorCode.RATE_LIMITED
        )

    @app.middleware("http")
    async def upload_cap(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """E10 SHOULD-1: refuse an oversized upload from its Content-Length, before multipart
        parsing. The route still checks the file itself (chunked bodies have no length)."""
        size = request.headers.get("content-length", "")
        cap = settings.max_upload_bytes + _MULTIPART_OVERHEAD
        if request.url.path.endswith("/files") and size.isdigit() and int(size) > cap:
            return problems.problem_response(
                request,
                413,
                f"file is larger than {settings.max_upload_bytes} bytes",
                ApiErrorCode.PAYLOAD_TOO_LARGE,
            )
        return await call_next(request)

    @app.middleware("http")
    async def request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = uuid.uuid4().hex
        with log_context(request_id=rid, tenant_id=settings.tenant_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    # Added last, so outermost: 429s and 500s still carry CORS headers for the web app (N2).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ui_origin_list,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )

    for module in (health, auth, cases, citations, lineage, workflow, admin):
        app.include_router(module.router)
    for name, agent_router, deps in _AGENT_ROUTERS:
        app.include_router(agent_router, prefix=f"/v1/agents/{name}")
        app.dependency_overrides[deps.get_supervisor] = lambda: svc.service
        app.dependency_overrides[deps.get_principal] = current_user
    app.openapi = lambda: _openapi(app)  # type: ignore[method-assign]
    return app


_MULTIPART_OVERHEAD = 64 * 1024  # boundaries and part headers around one file
_PROBLEM = {
    "type": "object",
    "required": ["type", "title", "status", "detail", "code"],
    "properties": {
        "type": {"type": "string"},
        "title": {"type": "string"},
        "status": {"type": "integer"},
        "detail": {"type": "string"},
        "code": {"type": "string"},
        "instance": {"type": "string"},
        "errors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field": {"type": ["string", "null"]},
                    "row": {"type": ["integer", "null"]},
                    "reason": {"type": "string"},
                },
            },
        },
    },
}


def _openapi(app: FastAPI) -> dict[str, Any]:
    """E10 SHOULD-2, scope #51: the schema says what the runtime does. Every error is RFC 9457
    problem+json (4XX, 5XX, and 422 in place of FastAPI's default), and the agent routers' case
    routes need the same bearer token as the core routes (their auth is a gateway override, which
    FastAPI cannot see)."""
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    components = schema.setdefault("components", {})
    components.setdefault("securitySchemes", {})["HTTPBearer"] = {
        "type": "http",
        "scheme": "bearer",
    }
    components.setdefault("schemas", {})["Problem"] = _PROBLEM
    problem = {
        "content": {
            "application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}
        }
    }
    for path, item in schema["paths"].items():
        for op in item.values():
            responses = op.setdefault("responses", {})
            if "422" in responses:
                responses["422"] = {"description": "Validation error", **problem}
            responses["4XX"] = {"description": "Client error", **problem}
            responses["5XX"] = {"description": "Server error", **problem}
            if path.startswith("/v1/agents/") and "/cases/" in path:
                op.setdefault("security", [{"HTTPBearer": []}])
    schema["components"]["schemas"].pop("HTTPValidationError", None)
    schema["components"]["schemas"].pop("ValidationError", None)
    app.openapi_schema = schema
    return schema


def app() -> FastAPI:
    """Uvicorn factory entry point (`--factory`)."""
    return create_app()


__all__: list[Any] = ["app", "build_services", "create_app"]
