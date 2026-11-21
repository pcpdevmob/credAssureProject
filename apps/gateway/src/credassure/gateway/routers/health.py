"""Liveness and readiness probes (scope #50) with the quota monitor (scope #16). No auth."""

from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from credassure.gateway.deps import Services, Svc
from credassure.gateway.quota import quota

router = APIRouter(prefix="/v1/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


def _index(svc: Services) -> str:
    """The copilot's vector index, checked on disk without loading it (no model, no query):
    `not_configured` in keyword mode, `missing` when `CHROMA_PATH` holds no index (run `make
    ingest` with the same MODELS), else `ok`. It is reported, not gated: gates, figures, routing
    and approval do not use the index; only cited copilot answers do."""
    settings = svc.settings
    if settings.copilot_search_mode == "keyword":
        return "not_configured"
    return "ok" if (settings.chroma_path / "chroma.sqlite3").is_file() else "missing"


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
        "chroma": _index(svc),
        "model": model,
        "quota": quota(svc) if db == "ok" else None,
    }
    healthy = db == "ok" and model != "open" and (checks["quota"] or {}).get("level") != "exhausted"
    return {"status": "ok" if healthy else "degraded", "checks": checks}
