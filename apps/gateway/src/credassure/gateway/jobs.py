"""Asynchronous runs (ADR 0007, scope #47): job row → background task → run lock + heartbeat.

`start` is idempotent per Idempotency-Key. `execute` claims the job (queued → running exactly
once), holds the case's run lock and refreshes it every HEARTBEAT; a run whose lock was taken
over (three missed beats) ends `abandoned`. Agent failures are the Supervisor's business (it
returns FAILED); anything else marks the job failed without leaking internals.
"""

import logging
import threading
from collections.abc import Callable
from typing import Any

from sqlalchemy import Engine

from credassure.agents.supervisor.graph import Supervisor
from credassure.core.enums import Stage
from credassure.ledger import reads
from credassure.ledger.models import Job
from credassure.ledger.session import (
    HEARTBEAT,
    RunInProgressError,
    heartbeat,
    run_lock,
    transaction,
)
from credassure.ledger.store import SqlLedger

_log = logging.getLogger("credassure.jobs")
NOT_RUNNABLE = frozenset({"AWAITING_APPROVAL", "HELD", "APPROVED", "REJECTED"})


class JobRunner:
    def __init__(
        self,
        engine: Engine,
        ledger: SqlLedger,
        supervisor: Supervisor,
        beat_seconds: float = HEARTBEAT.total_seconds(),
    ) -> None:
        self.engine, self.ledger, self.supervisor = engine, ledger, supervisor
        self.beat_seconds = beat_seconds

    def start(
        self,
        case_id: str,
        *,
        stage: Stage | None,
        idempotency_key: str | None,
        actor: str,
        schedule: Callable[..., Any],
    ) -> Job:
        job = self.ledger.create_job(
            case_id,
            kind="stage" if stage else "run",
            stage=stage.value if stage else None,
            idempotency_key=idempotency_key,
            actor=actor,
        )
        if job.status == "queued":
            schedule(self.execute, job.id, case_id, stage)
        return job

    def execute(self, job_id: str, case_id: str, stage: Stage | None) -> None:
        if not self.ledger.claim_job(job_id):
            return  # another task already runs (or ran) this job
        lost = threading.Event()
        try:
            with run_lock(self.engine, self.ledger.tenant_id, case_id, job_id):
                stop = threading.Event()

                def beat() -> None:
                    while not stop.wait(self.beat_seconds):
                        try:
                            alive = heartbeat(self.engine, case_id, job_id)
                        except Exception:  # e.g. database locked: assume the lock is gone
                            _log.warning("heartbeat failed for job %s", job_id, exc_info=True)
                            alive = False
                        if not alive:
                            lost.set()
                            return

                thread = threading.Thread(target=beat, name=f"heartbeat-{job_id}", daemon=True)
                thread.start()
                try:
                    self._resume_recorded_return(case_id)
                    outcome = self.supervisor.run(case_id, stage=stage, cancelled=lost.is_set)
                finally:
                    stop.set()
                    thread.join()
            status = "abandoned" if lost.is_set() or outcome.status == "ABANDONED" else "succeeded"
            self.ledger.update_job(job_id, status=status, outcome=outcome.status)
        except RunInProgressError:
            self.ledger.update_job(job_id, status="failed", error="another run holds this case")
        except Exception as exc:
            _log.exception("job %s failed", job_id)
            self.ledger.update_job(job_id, status="failed", error=type(exc).__name__)

    def _resume_recorded_return(self, case_id: str) -> None:
        """The ledger is the authority (APR-04): if it holds a return the graph never received
        (crash between the two writes), deliver it now so only the returned stage re-runs."""
        with transaction(self.engine) as s:
            case = reads.get_case(s, self.ledger.tenant_id, case_id)
        if case is None or case.status != "RETURNED" or case.current_stage is None:
            return
        # Not waiting at the interrupt means the return was already delivered.
        if self.supervisor.awaiting_decision(case_id):
            self.supervisor.decide(
                case_id, decision="return", return_stage=Stage(case.current_stage)
            )


def job_view(job: Job) -> dict[str, Any]:
    return {
        "job_id": job.id,
        "case_id": job.case_id,
        "kind": job.kind,
        "stage": job.stage,
        "status": job.status,
        "outcome": job.outcome,
        "error": job.error,
        "status_url": f"/v1/jobs/{job.id}",
        "events_url": f"/v1/jobs/{job.id}/events",
    }
