"""HTTP surface mounted at /v1/agents/supervisor (ADR 0005, scope #28).

Every case route goes through the Supervisor service with the authenticated caller; gates,
caps, case policy and audit always apply. No route accepts, signs or submits a lender offer.
"""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException

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


@router.post("/cases/{case_id}/stages/{stage}/retry", status_code=202)
def retry(
    case_id: str,
    stage: Literal["onboarding", "working_capital", "lendwise", "critic"],
    who: Caller,
    supervisor: SupervisorDep,
    background: BackgroundTasks,
) -> dict[str, Any]:
    """Evaluator only (scope #25): re-run one stage of a FAILED case as a stage job (202 + job).
    Upstream gates, caps and audit apply exactly as for any run (SUP-03, SUP-07)."""
    return supervisor.retry_stage(who, case_id, stage, schedule=background.add_task)
