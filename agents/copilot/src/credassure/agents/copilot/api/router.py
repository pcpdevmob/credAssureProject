"""HTTP surface mounted at /v1/agents/copilot (ADR 0005, scope #28).

Every case route goes through the Supervisor service with the authenticated caller; gates,
caps, case policy and audit always apply. No route accepts, signs or submits a lender offer.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException

from credassure.agents.copilot import __version__
from credassure.agents.copilot.api.deps import get_principal, get_supervisor
from credassure.core.ports import SupervisorPort

router = APIRouter(tags=["copilot"])
SupervisorDep = Annotated[SupervisorPort, Depends(get_supervisor)]
Caller = Annotated[Any, Depends(get_principal)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]
STAGE = None


@router.get("/card")
def card() -> dict[str, Any]:
    """Agent card: name, version and the stage it runs (if any)."""
    return {"name": "copilot", "version": __version__, "stage": STAGE}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "copilot"}


@router.post("/cases/{case_id}/chat")
def chat(
    case_id: str, body: dict[str, str], who: Caller, supervisor: SupervisorDep
) -> dict[str, Any]:
    """Ask the copilot about this case: refusal in code, cited answer or the abstention."""
    message = body.get("message", "")
    if not message or len(message) > 4000:
        raise HTTPException(status_code=422, detail="message must be 1-4000 characters")
    return supervisor.chat(who, case_id, message)
