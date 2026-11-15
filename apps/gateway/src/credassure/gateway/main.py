"""Gateway app factory: the composition root (ADR 0005, ADR 0006, scope #28 /v1, #46).

Builds the adapters (case.db engine, SqlLedger, LangGraph SqliteSaver, LLM or none), injects
them into the Supervisor with the stage agents, and mounts the /v1 routers plus each agent's
router at /v1/agents/<name>. Agent routers reach the Supervisor only through the service.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from decimal import Decimal
from typing import Any

import yaml
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
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
from credassure.core.enums import AgentName, Stage
from credassure.core.errors import ApiErrorCode
from credassure.core.money import from_paise
from credassure.core.ports import LLMPort, ToolPort
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
from credassure.gateway.routers import admin, auth, cases, health, workflow
from credassure.gateway.settings import Settings, get_settings
from credassure.gateway.supervisor_service import SupervisorService
from credassure.ledger import hr, migrate, reads
from credassure.ledger.session import case_engine, hr_engine, transaction
from credassure.ledger.store import SqlLedger
from credassure.observability.log import configure_logging, log_context, set_redactor
from credassure.security import pii
from credassure.security.auth import verify_token
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


def _lendwise_handlers(settings: Settings, engine: Engine) -> dict[str, Callable[..., Any]]:
    """LW engines as tools. Pure calls; only load_offers reads the case (SUP-08)."""
    load = _offer_inputs(settings, engine)
    gst, convention = settings.gst_rate, settings.apr_convention

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
    }

    # ponytail: other agents get no handlers until Phases 9d-9e register their engines here.
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

    for module in (health, auth, cases, workflow, admin):
        app.include_router(module.router)
    for name, agent_router, deps in _AGENT_ROUTERS:
        app.include_router(agent_router, prefix=f"/v1/agents/{name}")
        app.dependency_overrides[deps.get_supervisor] = lambda: svc.service
        app.dependency_overrides[deps.get_principal] = current_user
    return app


def app() -> FastAPI:
    """Uvicorn factory entry point (`--factory`)."""
    return create_app()


__all__: list[Any] = ["app", "build_services", "create_app"]
