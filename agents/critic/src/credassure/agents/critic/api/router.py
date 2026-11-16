"""HTTP surface mounted at /v1/agents/critic (ADR 0005, scope #28).

Every case route goes through the Supervisor service with the authenticated caller; gates,
caps, case policy and audit always apply. No route accepts, signs or submits a lender offer.
"""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException

from credassure.agents.critic import __version__
from credassure.agents.critic.api.deps import get_principal, get_supervisor
from credassure.core.ports import SupervisorPort

router = APIRouter(tags=["critic"])
SupervisorDep = Annotated[SupervisorPort, Depends(get_supervisor)]
Caller = Annotated[Any, Depends(get_principal)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]
STAGE = "critic"


@router.get("/card")
def card() -> dict[str, Any]:
    """Agent card: name, version and the stage it runs (if any)."""
    return {"name": "critic", "version": __version__, "stage": STAGE}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "critic"}


@router.post("/cases/{case_id}/run", status_code=202)
def run_stage(
    case_id: str,
    who: Caller,
    supervisor: SupervisorDep,
    background: BackgroundTasks,
    idempotency_key: IdempotencyKey = None,
) -> dict[str, Any]:
    """Run only this stage through the Supervisor (earlier stages must be GO, SUP-03)."""
    return supervisor.start_run(
        who, case_id, stage=STAGE, idempotency_key=idempotency_key, schedule=background.add_task
    )


@router.get("/cases/{case_id}/result")
def result(case_id: str, who: Caller, supervisor: SupervisorDep) -> dict[str, Any]:
    """Latest AgentResult for this stage (404 before the first run)."""
    found = supervisor.latest_result(who, case_id, STAGE)
    if found is None:
        raise HTTPException(status_code=404, detail="no result yet")
    return found.model_dump(mode="json")


@router.get("/cases/{case_id}/findings")
def findings(case_id: str, who: Caller, supervisor: SupervisorDep) -> dict[str, Any]:
    """VER-01..04: the latest Critic findings and the stage each one reopens (404 before a run)."""
    found = supervisor.latest_result(who, case_id, STAGE)
    if found is None:
        raise HTTPException(status_code=404, detail="no result yet")
    return {
        "decision": found.decision.value,
        "findings": [
            {"code": b.code.value, "message": b.message, "stage": b.field} for b in found.blockers
        ],
        "trace_id": found.trace_id,
    }
