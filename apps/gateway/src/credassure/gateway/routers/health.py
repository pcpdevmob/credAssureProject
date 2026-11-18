"""Liveness and readiness probes (scope #50) with the quota monitor (scope #16). No auth."""

from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from credassure.gateway.deps import Svc
from credassure.gateway.quota import quota

router = APIRouter(prefix="/v1/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(svc: Svc) -> dict[str, Any]:
    try:
        with svc.engine.connect() as c:
            c.execute(text("SELECT 1"))
        db = "ok"
    except Exception:
        db = "error"
    model = "disabled" if svc.llm is None else str(getattr(svc.llm, "circuit_state", "closed"))
    if svc.llm is not None and getattr(svc.llm, "replay", False) is True and model == "closed":
        model = "replay"  # recorded replies only (scope #17, ADR 0015)
    checks: dict[str, Any] = {
        "db": db,
        "chroma": "not_configured",  # Phase 7 adds the embedded Chroma client
        "model": model,
        "quota": quota(svc) if db == "ok" else None,
    }
    healthy = db == "ok" and model != "open" and (checks["quota"] or {}).get("level") != "exhausted"
    return {"status": "ok" if healthy else "degraded", "checks": checks}
