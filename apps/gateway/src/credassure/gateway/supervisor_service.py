"""The SupervisorPort the agent routers use (ADR 0005 rule 3, ADR 0006).

Agent routers never touch an agent or the database: they hand the authenticated principal to
this service, which applies the same case policy and job runner as the core /v1 routes.
"""

import uuid
from collections.abc import Callable
from typing import Any

from credassure.core.enums import Stage
from credassure.core.errors import ApiErrorCode
from credassure.core.results import AgentResult
from credassure.gateway.deps import Services, own_case, visible_case
from credassure.gateway.jobs import NOT_RUNNABLE, job_view
from credassure.gateway.problems import ProblemError
from credassure.ledger import reads
from credassure.ledger.session import run_in_progress, transaction
from credassure.observability.tracing import span
from credassure.security import pii
from credassure.security.auth import Principal

PII_NOTICE = (
    "Personal identifiers ({kinds}) are not accepted in chat; they were removed and not stored "
    "(data-handling policy, DPDP Act 2023)."
)
UNAVAILABLE = (
    "The copilot is unavailable: cited, Critic-checked answers arrive with the copilot (Phase 9e)."
)


class SupervisorService:
    def __init__(self, svc: Services) -> None:
        self.svc = svc

    def start_run(
        self,
        actor: Principal,
        case_id: str,
        *,
        stage: str | None,
        idempotency_key: str | None,
        schedule: Callable[..., Any],
    ) -> dict[str, Any]:
        case = own_case(self.svc, actor, case_id)
        if (
            idempotency_key is not None
        ):  # a replay returns the original job, whatever happened since
            with transaction(self.svc.engine) as s:
                seen = reads.job_by_key(s, case.tenant_id, case.id, idempotency_key)
            if seen is not None:
                replay: dict[str, Any] = job_view(seen)
                return replay
        if case.status in NOT_RUNNABLE:
            raise ProblemError(409, f"case is {case.status}; nothing to run", ApiErrorCode.CONFLICT)
        if run_in_progress(self.svc.engine, case.id):  # fail fast; the job would only fail later
            raise ProblemError(
                409, "a run is in progress on this case", ApiErrorCode.RUN_IN_PROGRESS
            )
        job = self.svc.jobs.start(
            case.id,
            stage=Stage(stage) if stage else None,
            idempotency_key=idempotency_key,
            actor=actor.user_id,
            schedule=schedule,
        )
        view: dict[str, Any] = job_view(job)
        return view

    def latest_result(
        self, actor: Principal, case_id: str, stage: str | None
    ) -> AgentResult | None:
        case = visible_case(self.svc, actor, case_id)
        with transaction(self.svc.engine) as s:
            runs = [
                r
                for r in reads.stage_runs(s, case.tenant_id, case.id)
                if r.result_json and (stage is None or r.stage == stage)
            ]
        latest = runs[-1].result_json if runs else None
        return AgentResult.model_validate_json(latest) if latest else None

    def fact(self, actor: Principal, case_id: str, key: str) -> str | None:
        """Latest value of one ledger fact, under the same case policy as every read."""
        case = visible_case(self.svc, actor, case_id)
        with transaction(self.svc.engine) as s:
            found = reads.get_latest(s, case.tenant_id, case.id, key)
        return None if found is None else found.value_text

    def plan(self, actor: Principal, case_id: str) -> dict[str, Any]:
        case = visible_case(self.svc, actor, case_id)
        plan: dict[str, Any] = self.svc.supervisor.plan(case.id).model_dump(mode="json")
        return plan

    def chat(self, actor: Principal, case_id: str, message: str) -> dict[str, Any]:
        """Placeholder copilot (Phase 9e). No model text reaches the user before the Critic can
        check it (CP-01, VER-01), so this returns a fixed notice whether the model is on or off."""
        case = visible_case(self.svc, actor, case_id)
        trace_id = uuid.uuid4().hex
        kinds = sorted({hit.kind for hit in pii.find(message)})  # ONB-06: refuse and redact
        with span(  # E11 N1: the id names a span; only the redacted text is ever recorded
            "chat", trace_id=trace_id, case_id=case.id, message=pii.redact(message)[:2000]
        ):
            pass
        reply: dict[str, Any] = {
            "answer": UNAVAILABLE,
            "citations": [],
            "intent": "copilot_question",
            "trace_id": trace_id,
            "pii_redacted": bool(kinds),
        }
        if kinds:
            reply["notice"] = PII_NOTICE.format(kinds=", ".join(kinds))
        return reply
