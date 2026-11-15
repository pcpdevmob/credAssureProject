"""Gateway app factory: the composition root (ADR 0005, ADR 0006, scope #28 /v1, #46).

Builds the adapters (case.db engine, SqlLedger, LangGraph SqliteSaver, LLM or none), injects
them into the Supervisor with the stage agents, and mounts the /v1 routers plus each agent's
router at /v1/agents/<name>. Agent routers reach the Supervisor only through the service.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite import SqliteSaver
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

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
from credassure.agents.supervisor.graph import Supervisor
from credassure.agents.working_capital import agent as working_capital
from credassure.agents.working_capital.api import deps as working_capital_deps
from credassure.agents.working_capital.api.router import router as working_capital_router
from credassure.core.enums import AgentName, Stage
from credassure.core.errors import ApiErrorCode
from credassure.core.ports import LLMPort, ToolPort
from credassure.gateway import problems, tracing
from credassure.gateway.deps import Services, current_user
from credassure.gateway.jobs import JobRunner
from credassure.gateway.routers import admin, auth, cases, health, workflow
from credassure.gateway.settings import Settings, get_settings
from credassure.gateway.supervisor_service import SupervisorService
from credassure.ledger import migrate, reads
from credassure.ledger.session import case_engine, transaction
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
        http_client=httpx2.Client(verify=ssl.create_default_context(cafile=ca)) if ca else None,
    )


def _tools(agent: AgentName) -> ToolPort:
    # ponytail: no tool handlers yet; Phases 9a-9e register the engines per agent here.
    return ToolRunner(agent, {})


def build_services(settings: Settings, llm: LLMPort | None) -> Services:
    migrate.upgrade("case", settings.case_db)  # idempotent; seeds stay separate (#29)
    engine = case_engine(settings.case_db)
    ledger = SqlLedger(engine, settings.tenant_id)
    with transaction(engine) as s:
        rule = reads.get_config(s, settings.tenant_id, "boundary_rule") or settings.boundary_rule
    saver = SqliteSaver(sqlite3.connect(settings.case_db, check_same_thread=False))
    supervisor = Supervisor(
        agents=_STAGE_AGENTS,
        store=ledger,
        ledger=ledger,
        tools=_tools,
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
