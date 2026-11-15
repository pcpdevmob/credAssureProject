"""HTTP surface mounted at /v1/agents/working-capital (ADR 0005, scope #28).

Every case route goes through the Supervisor service with the authenticated caller; gates,
caps, case policy and audit always apply. No route accepts, signs or submits a lender offer.
"""

import json
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException

from credassure.agents.working_capital import __version__
from credassure.agents.working_capital.api.deps import get_principal, get_supervisor
from credassure.core.money import format_inr, to_paise
from credassure.core.ports import SupervisorPort

router = APIRouter(tags=["working_capital"])
SupervisorDep = Annotated[SupervisorPort, Depends(get_supervisor)]
Caller = Annotated[Any, Depends(get_principal)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]
STAGE = "working_capital"


@router.get("/card")
def card() -> dict[str, Any]:
    """Agent card: name, version and the stage it runs (if any)."""
    return {"name": "working_capital", "version": __version__, "stage": STAGE}


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": "working_capital"}


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


@router.get("/cases/{case_id}/cash-table")
def cash_table(case_id: str, who: Caller, supervisor: SupervisorDep) -> dict[str, Any]:
    """The weekly cash table behind the funding need (WC-03/04); 404 before a GO run.

    Money is `{paise, display}` like every API amount (ADR 0004)."""
    rows = supervisor.fact(who, case_id, "wc.cash_table")
    if rows is None or supervisor.fact(who, case_id, "wc.gate") != "GO":  # never a stale table
        raise HTTPException(status_code=404, detail="no cash table yet")

    def money(text: str) -> dict[str, Any]:
        value = Decimal(text)
        return {"paise": to_paise(value), "display": format_inr(value)}

    return {
        "case_id": case_id,
        "rows": [
            {"week": r["week"], **{k: money(r[k]) for k in ("inflow", "outflow", "cumulative")}}
            for r in json.loads(rows)
        ],
    }
