"""HTTP surface mounted at /v1/agents/onboarding (ADR 0005, scope #28).

Every case route goes through the Supervisor service with the authenticated caller; gates,
caps, case policy and audit always apply. No route accepts, signs or submits a lender offer.
"""

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException

from credassure.agents.onboarding import __version__
from credassure.agents.onboarding.agent import PROMPT
from credassure.agents.onboarding.api.deps import get_principal, get_supervisor
from credassure.core.ports import SupervisorPort
from credassure.core.prompts import prompt_version

router = APIRouter(tags=["onboarding"])
SupervisorDep = Annotated[SupervisorPort, Depends(get_supervisor)]
Caller = Annotated[Any, Depends(get_principal)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]
STAGE = "onboarding"


@router.get("/card")
def card() -> dict[str, Any]:
    """Agent card: name, version, the stage it runs and its prompt versions (scope #25, #36)."""
    return {
        "name": "onboarding",
        "version": __version__,
        "stage": STAGE,
        "prompts": {PROMPT: prompt_version(PROMPT)},
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "onboarding"}


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
