"""HTTP surface mounted at /v1/agents/onboarding (ADR 0005, scope #28)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from credassure.agents.onboarding.api.deps import get_supervisor
from credassure.core.ports import SupervisorPort

router = APIRouter(tags=["onboarding"])
SupervisorDep = Annotated[SupervisorPort, Depends(get_supervisor)]


def _unavailable(case_id: str, supervisor: SupervisorPort) -> None:
    try:
        supervisor.run_stage(case_id, "onboarding")
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.get("/card")
def card() -> dict[str, str]:
    """Agent card: name and version."""
    return {"name": "onboarding", "version": "0.1.0"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "onboarding"}


@router.post("/cases/{case_id}/run")
def run_stage(case_id: str, supervisor: SupervisorDep) -> None:
    """Run this stage through the Supervisor. Not implemented yet."""
    _unavailable(case_id, supervisor)


@router.get("/cases/{case_id}/result")
def result(case_id: str, supervisor: SupervisorDep) -> None:
    """Latest result. Not implemented yet."""
    _unavailable(case_id, supervisor)
