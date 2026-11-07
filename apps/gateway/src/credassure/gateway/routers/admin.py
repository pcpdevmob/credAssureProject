"""Evaluator-only administration (APR-03 boundary rule, audited) and evaluation runs (Phase 11)."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel

from credassure.core.errors import ApiErrorCode
from credassure.gateway.deps import Svc, role
from credassure.gateway.problems import ProblemError
from credassure.security.auth import Principal, Role

router = APIRouter(prefix="/v1", tags=["admin"])
Evaluator = Annotated[Principal, role(Role.EVALUATOR)]


class Config(BaseModel):
    key: Literal["boundary_rule"]
    value: Literal["hold", "director", "vp"]


@router.post("/admin/config")
def set_config(body: Config, who: Evaluator, svc: Svc) -> dict[str, Any]:
    svc.ledger.set_config(body.key, body.value, who.user_id)
    svc.supervisor.boundary_rule = body.value  # applies to the next routing in this process
    return {"key": body.key, "value": body.value}


@router.post("/eval/runs")
def start_eval(who: Evaluator) -> None:
    raise ProblemError(501, "evaluation runs arrive in Phase 11", ApiErrorCode.NOT_IMPLEMENTED)


@router.get("/eval/runs/{run_id}")
def get_eval(run_id: str, who: Evaluator) -> None:
    raise ProblemError(501, "evaluation runs arrive in Phase 11", ApiErrorCode.NOT_IMPLEMENTED)
