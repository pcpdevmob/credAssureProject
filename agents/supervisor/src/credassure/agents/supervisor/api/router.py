"""HTTP surface mounted at /v1/agents/supervisor (ADR 0005, scope #28).

Every case route goes through the Supervisor service with the authenticated caller; gates,
caps, case policy and audit always apply. No route accepts, signs or submits a lender offer.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException

from credassure.agents.supervisor import __version__
from credassure.agents.supervisor.api.deps import get_principal, get_supervisor
from credassure.core.ports import SupervisorPort

router = APIRouter(tags=["supervisor"])
SupervisorDep = Annotated[SupervisorPort, Depends(get_supervisor)]
Caller = Annotated[Any, Depends(get_principal)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]
STAGE = None


@router.get("/card")
def card() -> dict[str, Any]:
    """Agent card: name, version and the stage it runs (if any)."""
    return {"name": "supervisor", "version": __version__, "stage": STAGE}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "supervisor"}


@router.get("/cases/{case_id}/result")
def result(case_id: str, who: Caller, supervisor: SupervisorDep) -> dict[str, Any]:
    """Latest AgentResult of any stage (404 before the first run)."""
    found = supervisor.latest_result(who, case_id, STAGE)
    if found is None:
        raise HTTPException(status_code=404, detail="no result yet")
    return found.model_dump(mode="json")


@router.get("/cases/{case_id}/plan")
def plan(case_id: str, who: Caller, supervisor: SupervisorDep) -> dict[str, Any]:
    """The visible Plan for this case (scope #19)."""
    return supervisor.plan(who, case_id)


@router.post("/cases/{case_id}/stages/{stage}/retry")
def retry(case_id: str, stage: str, who: Caller) -> None:
    """Evaluator only (scope #25); the retry itself arrives in Phase 9."""
    if getattr(getattr(who, "role", None), "value", None) != "evaluator":
        raise HTTPException(status_code=403, detail="only an evaluator may retry a stage")
    raise HTTPException(status_code=501, detail="arrives in Phase 9")
