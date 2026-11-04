"""HTTP surface mounted at /v1/agents/working-capital (ADR 0005, scope #28)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from credassure.agents.working_capital.api.deps import get_supervisor
from credassure.core.ports import SupervisorPort

router = APIRouter(tags=["working-capital"])
SupervisorDep = Annotated[SupervisorPort, Depends(get_supervisor)]


def _unavailable(case_id: str, supervisor: SupervisorPort) -> None:
    try:
        supervisor.run_stage(case_id, "working_capital")
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.get("/card")
def card() -> dict[str, str]:
    """Agent card: name and version."""
    return {"name": "working_capital", "version": "0.1.0"}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "working_capital"}


@router.post("/cases/{case_id}/run")
def run_stage(case_id: str, supervisor: SupervisorDep) -> None:
    """Run this stage through the Supervisor. Not implemented yet."""
    _unavailable(case_id, supervisor)


@router.get("/cases/{case_id}/result")
def result(case_id: str, supervisor: SupervisorDep) -> None:
    """Latest result. Not implemented yet."""
    _unavailable(case_id, supervisor)


@router.get("/cases/{case_id}/cash-table")
def cash_table(case_id: str, supervisor: SupervisorDep) -> None:
    """Cash table. Not implemented until Phase 9b."""
    _unavailable(case_id, supervisor)
