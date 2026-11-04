"""Gateway app factory. Routers for each phase are mounted under /v1 (scope #28)."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, FastAPI, Request, Response

from credassure.gateway.settings import Settings, get_settings
from credassure.observability.log import configure_logging, log_context

health = APIRouter(prefix="/v1/health", tags=["health"])


@health.get("/live")
def live() -> dict[str, str]:
    """Liveness probe; readiness (DB, Chroma, model circuit) arrives in Phase 8 (scope #50)."""
    return {"status": "ok"}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="CredAssure API", version="0.1.0")
    app.state.settings = settings

    @app.middleware("http")
    async def request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = uuid.uuid4().hex
        with log_context(request_id=rid, tenant_id=settings.tenant_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    app.include_router(health)
    return app


def app() -> FastAPI:
    """Uvicorn factory entry point (`--factory`)."""
    return create_app()
