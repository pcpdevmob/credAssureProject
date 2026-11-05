"""The only module that inserts ledger facts, audit events and decisions (ADR 0005, import-linter).

Every function takes the caller's Session; session.transaction() commits a write and its audit
event together or neither (scope #49).
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from credassure.security.auth import DECIDABLE, may_decide_route

from .chain import GENESIS, canonical, hashed_fields, row_hash
from .models import Approval, AuditLog, Case, LedgerFact, User

DECISIONS = {"approve": "APPROVED", "reject": "REJECTED", "return": "RETURNED"}
FINAL = frozenset({"APPROVED", "REJECTED"})  # APR-04: nothing reopens these


class ConflictError(Exception):
    """Optimistic-concurrency or business-rule conflict (the API answers 409)."""


def _now() -> datetime:
    return datetime.now(UTC)


def append_audit(
    s: Session,
    *,
    tenant_id: str,
    case_id: str | None,
    actor: str,
    event_type: str,
    payload: dict[str, Any],
) -> AuditLog:
    """Next link of the chain. BEGIN IMMEDIATE (session.py) serialises writers, so seq is safe."""
    payload = canonical(payload)  # hash exactly what the JSON column will read back
    last = s.execute(select(AuditLog).order_by(AuditLog.seq.desc()).limit(1)).scalar_one_or_none()
    seq = 1 if last is None else last.seq + 1
    prev = GENESIS if last is None else last.hash
    ts = _now().isoformat(timespec="microseconds")
    fields = hashed_fields(seq, tenant_id, case_id, actor, event_type, payload, ts)
    row = AuditLog(
        seq=seq,
        tenant_id=tenant_id,
        case_id=case_id,
        actor=actor,
        event_type=event_type,
        payload=payload,
        prev_hash=prev,
        hash=row_hash(prev, fields),
        ts=ts,
    )
    s.add(row)
    s.flush()
    return row


def put_fact(
    s: Session,
    *,
    tenant_id: str,
    case_id: str,
    key: str,
    value: Decimal | int | str,
    unit: str,
    source_type: str,
    source_ref: str,
    produced_by: str,
    input_hash: str,
    actor: str,
) -> LedgerFact:
    """New version of a fact plus its FACT_WRITTEN audit event, in the caller's transaction."""
    if isinstance(value, float) or not isinstance(value, Decimal | int | str):
        raise TypeError("ledger values are Decimal, int or str, never float (BR-05)")
    current = s.scalar(
        select(func.max(LedgerFact.version)).where(
            LedgerFact.tenant_id == tenant_id, LedgerFact.case_id == case_id, LedgerFact.key == key
        )
    )
    fact = LedgerFact(
        tenant_id=tenant_id,
        case_id=case_id,
        key=key,
        version=(current or 0) + 1,
        value_text=str(value),
        unit=unit,
        source_type=source_type,
        source_ref=source_ref,
        produced_by=produced_by,
        input_hash=input_hash,
        created_at=_now(),
    )
    s.add(fact)
    s.flush()
    append_audit(
        s,
        tenant_id=tenant_id,
        case_id=case_id,
        actor=actor,
        event_type="FACT_WRITTEN",
        payload={
            "key": key,
            "version": fact.version,
            "value": fact.value_text,
            "unit": unit,
            "source_ref": source_ref,
            "produced_by": produced_by,
            "input_hash": input_hash,
        },
    )
    return fact


def add_user(
    s: Session,
    *,
    user_id: str,
    tenant_id: str,
    username: str,
    role: str,
    password_hash: str,
    emp_id: str | None = None,
) -> User:
    user = User(
        id=user_id,
        tenant_id=tenant_id,
        username=username,
        role=role,
        emp_id=emp_id,
        password_hash=password_hash,
        active=True,
    )
    s.add(user)
    s.flush()
    return user


def create_case(
    s: Session,
    *,
    tenant_id: str,
    case_id: str,
    msme_name: str,
    order_ref: str,
    order_value_paise: int,
    indicative_amount_paise: int,
    due_date: date,
    preparer_id: str,
) -> Case:
    case = Case(
        id=case_id,
        tenant_id=tenant_id,
        msme_name=msme_name,
        order_ref=order_ref,
        order_value_paise=order_value_paise,
        indicative_amount_paise=indicative_amount_paise,
        due_date=due_date,
        preparer_id=preparer_id,
        status="CREATED",
        created_at=_now(),
    )
    s.add(case)
    s.flush()
    append_audit(
        s,
        tenant_id=tenant_id,
        case_id=case_id,
        actor=preparer_id,
        event_type="CASE_CREATED",
        payload={"indicative_amount_paise": indicative_amount_paise, "order_ref": order_ref},
    )
    return case


def route_case(s: Session, *, tenant_id: str, case_id: str, route: str, actor: str) -> Case:
    """After the Critic GO (Supervisor, Phase 8): store the engine route and await the approver."""
    case = s.scalar(select(Case).where(Case.tenant_id == tenant_id, Case.id == case_id))
    if case is None:
        raise ConflictError(f"no case {case_id}")
    if case.status in FINAL:
        raise ConflictError(f"case is {case.status}; a final decision cannot be reopened")
    case.route = route
    case.status = "HELD" if route == "HELD" else "AWAITING_APPROVAL"
    case.current_stage = "approval"
    s.flush()
    append_audit(
        s,
        tenant_id=tenant_id,
        case_id=case_id,
        actor=actor,
        event_type="ROUTED",
        payload={"route": route, "status": case.status},
    )
    return case


def record_decision(
    s: Session,
    *,
    tenant_id: str,
    case_id: str,
    approver_id: str,
    role: str,
    expected_version: int,
    decision: str,
    return_stage: str | None,
    comment: str,
) -> Approval:
    """APR-04: insert-only approval + case status + audit, at the case version the approver saw.

    The gateway checks role and routing (security.auth.can_decide); this re-checks maker-checker
    so no code path can record a self-approval (APR-05).
    """
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {sorted(DECISIONS)}")
    if (decision == "return") != (return_stage is not None):
        raise ValueError("return needs a return_stage; approve and reject must not have one")
    case = s.scalar(select(Case).where(Case.tenant_id == tenant_id, Case.id == case_id))
    if case is None:
        raise ConflictError(f"no case {case_id}")
    if case.preparer_id == approver_id:
        raise ConflictError("an approver cannot decide their own case (maker-checker)")
    if case.status not in DECIDABLE:  # APR-04: a decision is final; nothing re-decides it
        raise ConflictError(f"case is {case.status}, not awaiting a decision")
    approver = s.get(User, approver_id)
    if approver is None or not approver.active or approver.tenant_id != tenant_id:
        raise ConflictError(f"unknown or inactive approver {approver_id}")
    if approver.role != role:  # the stored role comes from users, never from the caller alone
        raise ConflictError(f"approver {approver_id} is {approver.role}, not {role}")
    if not may_decide_route(role, case.route):
        raise ConflictError(f"role {role} may not decide a case routed to {case.route}")
    if case.row_version != expected_version:
        raise ConflictError(f"case changed (version {case.row_version}, not {expected_version})")
    approval = Approval(
        tenant_id=tenant_id,
        case_id=case_id,
        approver_id=approver_id,
        role=role,
        decision=decision,
        return_stage=return_stage,
        comment=comment,
        created_at=_now(),
        row_version=expected_version,
    )
    s.add(approval)
    case.status = DECISIONS[decision]
    if return_stage is not None:
        case.current_stage = return_stage
    try:
        s.flush()  # UPDATE ... WHERE row_version = expected: a concurrent decision loses here
    except StaleDataError as exc:
        raise ConflictError("case changed concurrently") from exc
    append_audit(
        s,
        tenant_id=tenant_id,
        case_id=case_id,
        actor=approver_id,
        event_type="DECISION_RECORDED",
        payload={
            "role": role,
            "decision": decision,
            "return_stage": return_stage,
            "comment": comment,
            "case_version": expected_version,
        },
    )
    return approval
