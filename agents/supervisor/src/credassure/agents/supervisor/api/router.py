"""HTTP surface mounted at /v1/agents/supervisor (ADR 0005, scope #28)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from credassure.agents.supervisor.api.deps import get_supervisor
from credassure.core.ports import SupervisorPort

router = APIRouter(tags=["supervisor"])
SupervisorDep = Annotated[SupervisorPort, Depends(get_supervisor)]


def _unavailable(case_id: str, supervisor: SupervisorPort) -> None:
    try:
        supervisor.run_stage(case_id, "supervisor")
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.get("/card")
def card() -> dict[str, str]:
    """Agent card: name and version."""
    return {"name": "supervisor", "version": "0.1.0"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "supervisor"}


@router.get("/cases/{case_id}/result")
def result(case_id: str, supervisor: SupervisorDep) -> None:
    """Latest result. Not implemented yet."""
    _unavailable(case_id, supervisor)


@router.get("/cases/{case_id}/plan")
def plan(case_id: str, supervisor: SupervisorDep) -> None:
    """Case plan. Not implemented until Phase 8."""
    _unavailable(case_id, supervisor)


@router.post("/cases/{case_id}/stages/{stage}/retry")
def retry(case_id: str, stage: str, supervisor: SupervisorDep) -> None:
    """Retry one stage. Not implemented until Phase 8."""
    _unavailable(case_id, supervisor)
