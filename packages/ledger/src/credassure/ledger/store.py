"""SqlLedger: the ledger adapter for LedgerPort and SupervisorStore (ADR 0006, scope #46).

Agents and the Supervisor reach case.db only through this class, never through writes.py
(ADR 0005 rule 5, import-linter). One instance is bound to one tenant; each call is one
transaction, so a fact or a stage result commits together with its audit event (scope #49).
"""

import hashlib
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine

from credassure.core.results import AgentResult

from . import reads, writes
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

    def route(self, case_id: str, route: str) -> None:
        with transaction(self.engine) as s:
            writes.route_case(
                s, tenant_id=self.tenant_id, case_id=case_id, route=route, actor=self.actor
            )
