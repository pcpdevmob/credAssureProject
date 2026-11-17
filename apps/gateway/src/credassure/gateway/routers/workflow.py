"""Runs, jobs, progress and decisions (SUP-01/03/06, APR-04/05, ADR 0003 §8, ADR 0007).

A run answers 202 with a job; progress is SSE polled from case.db. A decision is written by the
ledger first (maker-checker, routed role, row_version) and only then resumes the Supervisor.
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Header, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, SecretStr

from credassure.core.enums import Stage
from credassure.core.errors import ApiErrorCode, NoPendingApproval
from credassure.engines.routing import THRESHOLD
from credassure.gateway import report
from credassure.gateway.deps import Svc, User, case_ref, role, visible_case
from credassure.gateway.jobs import job_view
from credassure.gateway.problems import ProblemError
from credassure.gateway.quota import quota
from credassure.gateway.routers.auth import LOGIN_FAILURES
from credassure.gateway.supervisor_service import approval_warnings
from credassure.ledger import reads
from credassure.ledger.session import run_in_progress, run_lock, transaction
from credassure.security.auth import (
    APPROVER_ROUTES,
    DECIDABLE,
    Principal,
    Role,
    can_decide,
    may_decide_route,
    verify_password,
)
from credassure.security.pii import redact

router = APIRouter(prefix="/v1", tags=["workflow"])
Approver = Annotated[Principal, role(Role.DIRECTOR_FINANCE, Role.VP_FINANCE)]
_log = logging.getLogger("credassure.gateway")
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]
STEP_STAGES = {  # ADR 0003 §8 thin wrappers, one Supervisor stage each
    "readiness": Stage.ONBOARDING,
    "assessment": Stage.WORKING_CAPITAL,
    "proposal": Stage.LENDWISE,
    "verify": Stage.CRITIC,
}
SSE_POLL_SECONDS = 0.5
SSE_MAX_SECONDS = 600.0  # S5: a client re-subscribes after this; no stream lives forever
SSE_DEAD_GRACE = 5.0  # a running job with no live run lock this long has died
TERMINAL = frozenset({"succeeded", "failed", "abandoned"})


def start(
    svc: Svc,
    who: User,
    case_id: str,
    stage: Stage | None,
    key: str | None,
    background: BackgroundTasks,
    response: Response,
) -> dict[str, Any]:
    view = svc.service.start_run(
        who,
        case_id,
        stage=stage.value if stage else None,
        idempotency_key=key,
        schedule=background.add_task,
    )
    level = quota(svc)["level"]
    if level != "ok":
        response.headers["X-Quota-Warning"] = level
    response.headers["Location"] = view["status_url"]
    result: dict[str, Any] = view
    return result


@router.post("/cases/{case_id}/run", status_code=202)
def run(
    case_id: str,
    who: User,
    svc: Svc,
    background: BackgroundTasks,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> dict[str, Any]:
    return start(svc, who, case_id, None, idempotency_key, background, response)


def _step(name: str, stage: Stage) -> None:
    def endpoint(
        case_id: str,
        who: User,
        svc: Svc,
        background: BackgroundTasks,
        response: Response,
        idempotency_key: IdempotencyKey = None,
    ) -> dict[str, Any]:
        return start(svc, who, case_id, stage, idempotency_key, background, response)

    endpoint.__name__ = f"run_{name}"
    endpoint.__doc__ = f"Run only the {stage.value} stage; earlier stages must be GO (SUP-03)."
    router.add_api_route(f"/cases/{{case_id}}/{name}", endpoint, methods=["POST"], status_code=202)


for _name, _stage in STEP_STAGES.items():
    _step(_name, _stage)


def _job_for(svc: Svc, who: User, job_id: str) -> Any:
    with transaction(svc.engine) as s:
        job = reads.get_job(s, who.tenant_id, job_id)
    if job is None:
        raise ProblemError(404, f"no job {job_id}", ApiErrorCode.NOT_FOUND)
    visible_case(svc, who, job.case_id)  # same visibility as the case itself (404 otherwise)
    return job


@router.get("/jobs/{job_id}")
def get_job(job_id: str, who: User, svc: Svc) -> dict[str, Any]:
    view: dict[str, Any] = job_view(_job_for(svc, who, job_id))
    return view


@router.get("/jobs/{job_id}/events", response_class=StreamingResponse)
async def events(job_id: str, who: User, svc: Svc) -> StreamingResponse:
    """SSE: one `stage` event per stage run since the job started, then `end` (ADR 0007)."""
    job = _job_for(svc, who, job_id)

    def poll() -> tuple[Any, list[Any], bool]:  # blocking DB reads: run off the event loop
        with transaction(svc.engine) as s:
            current = reads.get_job(s, who.tenant_id, job_id)
            runs = [
                r
                for r in reads.stage_runs(s, who.tenant_id, job.case_id)
                if r.started_at >= job.created_at and r.ended_at is not None
            ]
        alive = current is not None and (
            current.status != "running" or run_in_progress(svc.engine, job.case_id)
        )
        return current, runs, alive

    async def stream() -> AsyncIterator[str]:
        sent: set[int] = set()
        started = last_alive = time.monotonic()
        while True:
            current, runs, alive = await run_in_threadpool(poll)
            now = time.monotonic()
            last_alive = now if alive else last_alive
            for r in runs:
                if r.id not in sent:
                    sent.add(r.id)
                    data = {"stage": r.stage, "decision": r.decision, "attempt": r.attempt}
                    yield f"event: stage\ndata: {json.dumps(data)}\n\n"
            status = current.status if current else "unknown"
            if current is not None and status not in TERMINAL:
                if now - last_alive > SSE_DEAD_GRACE:
                    status = "stale"  # the run died; ADR 0007 takeover re-runs it on next start
                elif now - started > SSE_MAX_SECONDS:
                    status = "timeout"
            if status in TERMINAL or status in {"stale", "timeout", "unknown"}:
                end = {"status": status, "outcome": current.outcome if current else None}
                yield f"event: end\ndata: {json.dumps(end)}\n\n"
                return
            await asyncio.sleep(SSE_POLL_SECONDS)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


# ---- approvals (UI-07, APR-04..06) -------------------------------------------------------------
def _approver(who: User) -> None:
    if who.role not in APPROVER_ROUTES:
        raise ProblemError(403, "only a finance approver may do this", ApiErrorCode.FORBIDDEN)


@router.get("/inbox")
def inbox(who: User, svc: Svc) -> dict[str, Any]:
    _approver(who)
    with transaction(svc.engine) as s:
        cases = reads.list_cases(s, who.tenant_id)
    items = [
        {"case_id": c.id, "msme_name": c.msme_name, "status": c.status, "route": c.route}
        for c in cases
        if c.status in DECIDABLE and may_decide_route(who.role.value, c.route)
    ]
    return {"items": items}


@router.get("/cases/{case_id}/inbox")
def case_inbox(case_id: str, who: User, svc: Svc) -> dict[str, Any]:
    case = visible_case(svc, who, case_id)
    return {
        "warnings": _warnings(svc, case),
        "case_id": case.id,
        "status": case.status,
        "route": case.route,
        "row_version": case.row_version,
        "can_decide": can_decide(who, case_ref(case)),
    }


def _warnings(svc: Svc, case: Any) -> list[str]:
    """APR-04 evidence for the approver. ``report_stale``: the figures changed after the routed
    proposal was rendered; it blocks approve (Phase 10b, ADR 0003 §3), not reject or return."""
    with transaction(svc.engine) as s:
        found = approval_warnings(reads.list_for_case(s, case.tenant_id, case.id))
        if report.state(s, case)["stale"]:
            found.append("report_stale")
    return found


class Decision(BaseModel):
    decision: Literal["approve", "reject", "return"]
    return_stage: Literal["onboarding", "working_capital", "lendwise"] | None = None
    comment: str = Field(default="", max_length=2000)
    expected_version: int = Field(ge=0, le=2**31 - 1)
    # NFR-07 step-up: the approver's own password, required to approve above ₹1.5 crore.
    password: SecretStr | None = Field(default=None, max_length=256)


def _step_up(
    svc: Svc, who: Principal, case: Any, password: SecretStr | None, request: Request
) -> None:
    """Re-authenticate an approval of more than the routing threshold (engines.routing.THRESHOLD,
    the same number routing uses). Failures share the login limit; 403, never 401, so the web
    client keeps the session. A missing validated amount fails closed (step-up required)."""
    with transaction(svc.engine) as s:
        gate = reads.get_latest(s, case.tenant_id, case.id, "wc.gate")
        need = reads.get_latest(s, case.tenant_id, case.id, "wc.recommended_amount")
        user = reads.get_user(s, who.user_id)
    if gate and gate.value_text == "GO" and need and Decimal(need.value_text) <= THRESHOLD:
        return
    limiter = request.app.state.login_limiter
    key = (f"step-up:{who.user_id}",)  # per user, not per IP: a stolen token cannot rotate IPs
    if not limiter.test(LOGIN_FAILURES, *key):
        raise ProblemError(
            429, "too many failed confirmations; wait a minute", ApiErrorCode.RATE_LIMITED
        )
    if (
        password is None
        or user is None
        or not verify_password(user.password_hash, password.get_secret_value())
    ):
        if password is not None:
            limiter.hit(LOGIN_FAILURES, *key)
            svc.ledger.audit(case.id, "STEP_UP_FAILED", {"by": who.user_id})
        raise ProblemError(
            403,
            "approving more than ₹1,50,00,000 needs your password again",
            ApiErrorCode.STEP_UP_REQUIRED,
        )
    svc.ledger.audit(case.id, "STEP_UP_VERIFIED", {"by": who.user_id})


@router.post("/cases/{case_id}/decision")
def decide(
    case_id: str, body: Decision, who: Approver, svc: Svc, request: Request
) -> dict[str, Any]:
    """Only the routed approver; never the preparer (maker-checker); internal only (APR-06)."""
    case = visible_case(svc, who, case_id)
    if not can_decide(who, case_ref(case)):
        raise ProblemError(403, "you may not decide this case", ApiErrorCode.FORBIDDEN)
    if (body.decision == "return") != (body.return_stage is not None):
        raise ProblemError(
            422,
            "return needs return_stage; approve and reject must not have one",
            errors=[{"field": "return_stage", "row": None, "reason": "inconsistent"}],
        )
    if body.decision == "approve" and svc.settings.approval_step_up:
        _step_up(svc, who, case, body.password, request)
    back = Stage(body.return_stage) if body.return_stage else None
    # One writer per case: a decision never races a running stage (ADR 0007).
    with run_lock(svc.engine, who.tenant_id, case.id, f"decision-{uuid.uuid4().hex}"):
        if back is not None and not svc.supervisor.awaiting_decision(case.id):
            # S1: fail closed. The return is not recorded as applied; the case is FAILED.
            svc.supervisor.fail_return(case.id, back)
            raise ProblemError(409, "no approval is pending for this case", ApiErrorCode.CONFLICT)
        if body.decision == "approve":  # under the lock: nothing changes between check and record
            with transaction(svc.engine) as s:
                stale = report.state(s, case)["stale"]
            if stale:  # #6: never approve figures the proposal the approver read does not show
                raise ProblemError(409, "report stale, regenerate", ApiErrorCode.REPORT_STALE)
        # NFR-07: the comment is redacted before it reaches the approval row and its audit event.
        approval = svc.ledger.record_decision(
            case.id,
            approver_id=who.user_id,
            role=who.role.value,
            expected_version=body.expected_version,
            decision=body.decision,
            return_stage=body.return_stage,
            comment=redact(body.comment),
            warnings=_warnings(svc, case),
        )
        try:
            svc.supervisor.decide(case.id, decision=body.decision, return_stage=back)
        except NoPendingApproval:  # approve/reject: the ledger record is the authority (APR-04)
            _log.warning("decision recorded but no pending approval interrupt for %s", case.id)
    with transaction(svc.engine) as s:
        fresh = reads.get_case(s, who.tenant_id, case.id)
    return {"status": fresh.status if fresh else None, "approval_id": approval.id}
