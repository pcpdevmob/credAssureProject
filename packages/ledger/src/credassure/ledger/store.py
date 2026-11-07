"""SqlLedger: the ledger adapter for LedgerPort and SupervisorStore (ADR 0006, scope #46).

Agents and the Supervisor reach case.db only through this class, never through writes.py
(ADR 0005 rule 5, import-linter). One instance is bound to one tenant; each call is one
transaction, so a fact or a stage result commits together with its audit event (scope #49).
"""

import hashlib
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine

from credassure.core.results import AgentResult

from . import reads, writes
from .models import Approval, Case, CaseFile, Job
from .session import transaction


class SqlLedger:
    def __init__(self, engine: Engine, tenant_id: str, actor: str = "supervisor") -> None:
        self.engine, self.tenant_id, self.actor = engine, tenant_id, actor

    # LedgerPort
    def get(self, case_id: str, key: str) -> str | None:
        with transaction(self.engine) as s:
            fact = reads.get_latest(s, self.tenant_id, case_id, key)
            return None if fact is None else fact.value_text

    def put_fact(
        self,
        case_id: str,
        key: str,
        value: Decimal | int | str,
        *,
        unit: str,
        source_type: str,
        source_ref: str,
        produced_by: str,
    ) -> int:
        with transaction(self.engine) as s:
            fact = writes.put_fact(
                s,
                tenant_id=self.tenant_id,
                case_id=case_id,
                key=key,
                value=value,
                unit=unit,
                source_type=source_type,
                source_ref=source_ref,
                produced_by=produced_by,
                input_hash=hashlib.sha256(str(value).encode()).hexdigest(),
                actor=self.actor,
            )
            return fact.version

    # SupervisorStore
    def stage_started(self, case_id: str, stage: str, trace_id: str) -> int:
        with transaction(self.engine) as s:
            run = writes.start_stage_run(
                s, tenant_id=self.tenant_id, case_id=case_id, stage=stage, trace_id=trace_id
            )
            return run.id

    def stage_finished(self, run_id: int, result: AgentResult) -> None:
        with transaction(self.engine) as s:
            writes.finish_stage_run(
                s,
                tenant_id=self.tenant_id,
                run_id=run_id,
                decision=result.decision.value,
                result_json=result.model_dump_json(),
                actor=self.actor,
            )

    def set_state(self, case_id: str, *, status: str, current_stage: str | None) -> None:
        with transaction(self.engine) as s:
            writes.set_case_state(
                s,
                tenant_id=self.tenant_id,
                case_id=case_id,
                status=status,
                current_stage=current_stage,
                actor=self.actor,
            )

    def audit(self, case_id: str, event_type: str, payload: dict[str, Any]) -> None:
        with transaction(self.engine) as s:
            writes.append_audit(
                s,
                tenant_id=self.tenant_id,
                case_id=case_id,
                actor=self.actor,
                event_type=event_type,
                payload=payload,
            )

    def route(self, case_id: str, route: str, reason: str | None = None) -> None:
        with transaction(self.engine) as s:
            writes.route_case(
                s,
                tenant_id=self.tenant_id,
                case_id=case_id,
                route=route,
                actor=self.actor,
                reason=reason,
            )

    # Gateway commands (each one transaction with its audit event)
    def create_case(
        self,
        *,
        year: int,
        msme_name: str,
        order_ref: str,
        order_value_paise: int,
        indicative_amount_paise: int,
        due_date: date,
        preparer_id: str,
    ) -> Case:
        with transaction(self.engine) as s:
            return writes.create_case(
                s,
                tenant_id=self.tenant_id,
                case_id=writes.next_case_id(s, tenant_id=self.tenant_id, year=year),
                msme_name=msme_name,
                order_ref=order_ref,
                order_value_paise=order_value_paise,
                indicative_amount_paise=indicative_amount_paise,
                due_date=due_date,
                preparer_id=preparer_id,
            )

    def store_case_file(
        self, case_id: str, kind: str, payload_json: str, uploaded_by: str, *, sha256: str
    ) -> CaseFile:
        with transaction(self.engine) as s:
            return writes.store_case_file(
                s,
                tenant_id=self.tenant_id,
                case_id=case_id,
                kind=kind,
                payload_json=payload_json,
                uploaded_by=uploaded_by,
                sha256=sha256,
            )

    def record_decision(
        self,
        case_id: str,
        *,
        approver_id: str,
        role: str,
        expected_version: int,
        decision: str,
        return_stage: str | None,
        comment: str,
    ) -> Approval:
        with transaction(self.engine) as s:
            return writes.record_decision(
                s,
                tenant_id=self.tenant_id,
                case_id=case_id,
                approver_id=approver_id,
                role=role,
                expected_version=expected_version,
                decision=decision,
                return_stage=return_stage,
                comment=comment,
            )

    def create_job(
        self, case_id: str, *, kind: str, stage: str | None, idempotency_key: str | None, actor: str
    ) -> Job:
        with transaction(self.engine) as s:
            return writes.create_job(
                s,
                tenant_id=self.tenant_id,
                case_id=case_id,
                kind=kind,
                stage=stage,
                idempotency_key=idempotency_key,
                actor=actor,
            )

    def update_job(
        self, job_id: str, *, status: str, outcome: str | None = None, error: str | None = None
    ) -> Job:
        with transaction(self.engine) as s:
            return writes.update_job(s, job_id, status=status, outcome=outcome, error=error)

    def set_config(self, key: str, value: str, actor: str) -> None:
        with transaction(self.engine) as s:
            writes.upsert_config(s, tenant_id=self.tenant_id, key=key, value=value, actor=actor)

    def claim_job(self, job_id: str) -> bool:
        with transaction(self.engine) as s:  # BEGIN IMMEDIATE: only one claimer wins
            return writes.claim_job(s, job_id)

    def set_password_hash(self, user_id: str, password_hash: str) -> None:
        with transaction(self.engine) as s:
            writes.set_password_hash(s, user_id=user_id, password_hash=password_hash)
