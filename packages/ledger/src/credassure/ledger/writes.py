"""The only module that inserts ledger facts, audit events and decisions (ADR 0005, import-linter).

Every function takes the caller's Session; session.transaction() commits a write and its audit
event together or neither (scope #49).
"""

import json
import uuid
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CursorResult, func, inspect, select, text
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from credassure.core.seeded import SEEDED_CASE_MAX
from credassure.security.auth import DECIDABLE, may_decide_route

from .chain import GENESIS, canonical, hashed_fields, row_hash
from .errors import ConflictError
from .models import (
    AppConfig,
    Approval,
    AuditHead,
    AuditLog,
    Case,
    CaseFile,
    ChatMessage,
    Job,
    LedgerFact,
    StageRun,
    User,
)
from .reads import DELETED, verify_chain

DECISIONS = {"approve": "APPROVED", "reject": "REJECTED", "return": "RETURNED"}
FINAL = frozenset({"APPROVED", "REJECTED"})  # APR-04: nothing reopens these


_PROVENANCE = frozenset({"agent", "stage", "trace_id"})


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
    """Next link of the chain. BEGIN IMMEDIATE (SQLite) or the write-lock row (MySQL, ADR 0039)
    serialises writers, so seq is safe."""
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
    head = s.get(AuditHead, tenant_id)  # OBJ-08 tail anchor, same transaction as the row
    if head is None:
        s.add(AuditHead(tenant_id=tenant_id, seq=seq, hash=row.hash))
    else:
        head.seq, head.hash = seq, row.hash
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
    provenance: Mapping[str, str] | None = None,
) -> LedgerFact:
    """New version of a fact plus its FACT_WRITTEN audit event, in the caller's transaction."""
    if isinstance(value, float) or not isinstance(value, Decimal | int | str):
        raise TypeError("ledger values are Decimal, int or str, never float (BR-05)")
    latest = s.scalar(
        select(LedgerFact)
        .where(
            LedgerFact.tenant_id == tenant_id, LedgerFact.case_id == case_id, LedgerFact.key == key
        )
        .order_by(LedgerFact.version.desc())
        .limit(1)
    )
    current = latest.version if latest is not None else None
    if latest is not None and (
        latest.value_text,
        latest.unit,
        latest.source_type,
        latest.source_ref,
        latest.produced_by,
        latest.input_hash,
    ) == (str(value), unit, source_type, source_ref, produced_by, input_hash):
        return latest  # 9d: an identical re-run adds no version and no event
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
            # lineage (#33): who wrote it; only these three keys, never free text
            **{k: str(v) for k, v in (provenance or {}).items() if k in _PROVENANCE},
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
        created_at=_now(),
    )
    s.add(user)
    s.flush()
    return user


# ---- accounts (ADR 0038) ------------------------------------------------------------------------
ACCOUNT_EVENTS = frozenset(
    {
        "USER_CREATED",
        "USER_ROLE_CHANGED",
        "USER_DISABLED",
        "USER_ENABLED",
        "PASSWORD_RESET",
        "PASSWORD_CHANGED",
        "MFA_ENROLLED",
        "MFA_RESET",
        "BACKUP_CODE_USED",
        "LOGIN_FAILED",
        "SIGNED_OUT",
    }
)
# What an account change may set, and what its audit payload may say: never a hash, a code or a
# secret (only the field names that changed).
_USER_FIELDS = frozenset(
    {
        "role",
        "active",
        "display_name",
        "password_hash",
        "must_change_password",
        "mfa_enabled",
        "mfa_secret",
        "mfa_last_step",
        "mfa_backup",
    }
)
_ACCOUNT_PAYLOAD = frozenset({"user_id", "username", "role", "from_role", "by", "reason"})


def create_user(
    s: Session,
    *,
    tenant_id: str,
    actor: str,
    username: str,
    role: str,
    password_hash: str,
    display_name: str | None = None,
    emp_id: str | None = None,
    must_change_password: bool = True,
) -> User:
    """An account made by an admin (or the bootstrap command): temporary password, audited."""
    # Usernames are global: sign-in names no tenant, so one name is one person everywhere.
    if s.scalar(select(User.id).where(User.username == username)) is not None:
        raise ConflictError(f"username {username} is taken")
    if emp_id is not None and s.scalar(  # one login per HR profile (ONB-01)
        select(User.id).where(User.tenant_id == tenant_id, User.emp_id == emp_id)
    ):
        raise ConflictError(f"HR id {emp_id} is already bound to another user")
    user = add_user(
        s,
        user_id=f"u-{uuid.uuid4().hex[:12]}",
        tenant_id=tenant_id,
        username=username,
        role=role,
        password_hash=password_hash,
        emp_id=emp_id,
    )
    user.display_name, user.must_change_password = display_name, must_change_password
    s.flush()
    append_audit(
        s,
        tenant_id=tenant_id,
        case_id=None,
        actor=actor,
        event_type="USER_CREATED",
        payload={"user_id": user.id, "username": username, "role": role},
    )
    return user


def update_user(
    s: Session,
    *,
    user_id: str,
    tenant_id: str,
    actor: str,
    changes: Mapping[str, Any],
    event_type: str | None = None,
    payload: Mapping[str, Any] | None = None,
    revoke: bool = False,
) -> User:
    """Apply allow-listed changes; `revoke` bumps token_version so every issued token dies at once;
    `event_type` (an ACCOUNT_EVENTS name) appends one audit row naming the fields, not values."""
    user = s.get(User, user_id)
    if user is None or user.tenant_id != tenant_id:
        raise ConflictError(f"no user {user_id}")
    unknown = set(changes) - _USER_FIELDS
    if unknown:
        raise ValueError(f"not an account field: {sorted(unknown)}")
    for key, value in changes.items():
        setattr(user, key, value)
    if revoke:
        user.token_version = (user.token_version or 0) + 1
    user.updated_at = _now()
    s.flush()
    if event_type is not None:
        if event_type not in ACCOUNT_EVENTS:
            raise ValueError(f"not an account event: {event_type}")
        body = {k: v for k, v in (payload or {}).items() if k in _ACCOUNT_PAYLOAD}
        body |= {"user_id": user.id, "username": user.username, "fields": sorted(changes)}
        append_audit(
            s, tenant_id=tenant_id, case_id=None, actor=actor, event_type=event_type, payload=body
        )
    return user


def account_event(
    s: Session, *, tenant_id: str, actor: str, event_type: str, payload: Mapping[str, Any]
) -> None:
    """An account event with no field change (a failed login): same allow-list as update_user."""
    if event_type not in ACCOUNT_EVENTS:
        raise ValueError(f"not an account event: {event_type}")
    body = {k: v for k, v in payload.items() if k in _ACCOUNT_PAYLOAD}
    append_audit(
        s, tenant_id=tenant_id, case_id=None, actor=actor, event_type=event_type, payload=body
    )


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


def route_case(
    s: Session,
    *,
    tenant_id: str,
    case_id: str,
    route: str,
    actor: str,
    reason: str | None = None,
) -> Case:
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
        payload={"route": route, "status": case.status} | ({"reason": reason} if reason else {}),
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
    warnings: list[str] | None = None,
    attested: bool = False,
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
            "evidence_warnings": warnings or [],  # what the approver was shown (ADR 0023)
            "attested": attested,  # P9: "I reviewed the Critic findings" (plan v3.4 §6, ASI09)
        },
    )
    return approval


def set_case_state(
    s: Session, *, tenant_id: str, case_id: str, status: str, current_stage: str | None, actor: str
) -> Case:
    """Workflow status set by the Supervisor (PAUSED, FAILED, IN_PROGRESS); never a decision."""
    case = s.scalar(select(Case).where(Case.tenant_id == tenant_id, Case.id == case_id))
    if case is None:
        raise ConflictError(f"no case {case_id}")
    if case.status in FINAL:
        raise ConflictError(f"case is {case.status}; a final decision cannot be reopened")
    case.status, case.current_stage = status, current_stage
    s.flush()
    append_audit(
        s,
        tenant_id=tenant_id,
        case_id=case_id,
        actor=actor,
        event_type="STATE_CHANGED",
        payload={"status": status, "current_stage": current_stage},
    )
    return case


def start_stage_run(
    s: Session, *, tenant_id: str, case_id: str, stage: str, trace_id: str
) -> StageRun:
    attempts = s.scalar(
        select(func.count()).where(
            StageRun.tenant_id == tenant_id, StageRun.case_id == case_id, StageRun.stage == stage
        )
    )
    run = StageRun(
        tenant_id=tenant_id,
        case_id=case_id,
        stage=stage,
        attempt=(attempts or 0) + 1,
        trace_id=trace_id,
        started_at=_now(),
    )
    s.add(run)
    s.flush()
    return run


def finish_stage_run(
    s: Session, *, tenant_id: str, run_id: int, decision: str, result_json: str, actor: str
) -> StageRun:
    run = s.get(StageRun, run_id)
    if run is None or run.tenant_id != tenant_id:
        raise ConflictError(f"no stage run {run_id}")
    run.decision, run.result_json, run.ended_at = decision, result_json, _now()
    s.flush()
    append_audit(
        s,
        tenant_id=tenant_id,
        case_id=run.case_id,
        actor=actor,
        event_type="STAGE_COMPLETED",
        payload={"stage": run.stage, "attempt": run.attempt, "decision": decision},
    )
    return run


def create_job(
    s: Session,
    *,
    tenant_id: str,
    case_id: str,
    kind: str,
    stage: str | None,
    idempotency_key: str | None,
    actor: str,
) -> Job:
    """New queued job, or the existing one for the same Idempotency-Key (ADR 0007)."""
    if idempotency_key is not None:
        existing = s.scalar(
            select(Job).where(
                Job.tenant_id == tenant_id,
                Job.case_id == case_id,
                Job.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
    now = _now()
    job = Job(
        id=uuid.uuid4().hex,
        tenant_id=tenant_id,
        case_id=case_id,
        kind=kind,
        stage=stage,
        idempotency_key=idempotency_key,
        status="queued",
        created_by=actor,
        created_at=now,
        updated_at=now,
    )
    s.add(job)
    s.flush()
    return job


def update_job(
    s: Session, job_id: str, *, status: str, outcome: str | None = None, error: str | None = None
) -> Job:
    job = s.get(Job, job_id)
    if job is None:
        raise ConflictError(f"no job {job_id}")
    job.status, job.updated_at = status, _now()
    if outcome is not None:
        job.outcome = outcome
    if error is not None:
        job.error = error
    s.flush()
    return job


def next_case_id(s: Session, *, tenant_id: str, year: int) -> str:
    """CA-YYYY-NNNN, allocated inside the caller's BEGIN IMMEDIATE transaction (no race).

    `cases.id` is a global key, so the counter spans every tenant (`tenant_id` is kept for the
    caller's audit trail), and it starts after the highest seeded synthetic case: a live case never
    shares an ID with a seeded case or that case's synthetic KFS documents (SUP-08, BR-14).
    """
    del tenant_id
    prefix = f"CA-{year}-"
    last = s.scalar(select(func.max(Case.id)).where(Case.id.like(prefix + "%")))
    used = int(last.rsplit("-", 1)[1]) if last else 0
    return f"{prefix}{max(used, SEEDED_CASE_MAX.get(year, 0)) + 1:04d}"


def store_case_file(
    s: Session,
    *,
    tenant_id: str,
    case_id: str,
    kind: str,
    payload_json: str,
    uploaded_by: str,
    sha256: str,
) -> CaseFile:
    """New version of one case file (newest wins; old kept) plus its FILE_UPLOADED event.

    `sha256` is the hash of the bytes as uploaded, so the file can be matched to its source.
    """
    found = s.scalar(select(Case.status).where(Case.tenant_id == tenant_id, Case.id == case_id))
    if found == DELETED:  # ADR 0025: nothing is written into a tombstone
        raise ConflictError(f"case {case_id} is deleted")
    digest = sha256
    row = CaseFile(
        tenant_id=tenant_id,
        case_id=case_id,
        kind=kind,
        schema_version="1.0",
        sha256=digest,
        payload_json=payload_json,
        uploaded_by=uploaded_by,
        created_at=_now(),
    )
    s.add(row)
    s.flush()
    append_audit(
        s,
        tenant_id=tenant_id,
        case_id=case_id,
        actor=uploaded_by,
        event_type="FILE_UPLOADED",
        payload={"kind": kind, "sha256": digest},
    )
    return row


def upsert_config(s: Session, *, tenant_id: str, key: str, value: str, actor: str) -> AppConfig:
    """Admin setting (APR-03 boundary rule), audited."""
    row = s.get(AppConfig, (tenant_id, key))
    if row is None:
        row = AppConfig(
            tenant_id=tenant_id, key=key, value=value, updated_by=actor, updated_at=_now()
        )
        s.add(row)
    else:
        row.value, row.updated_by, row.updated_at = value, actor, _now()
    s.flush()
    append_audit(
        s,
        tenant_id=tenant_id,
        case_id=None,
        actor=actor,
        event_type="CONFIG_CHANGED",
        payload={"key": key, "value": value},
    )
    return row


def claim_job(s: Session, job_id: str) -> bool:
    """queued → running exactly once; a duplicate background task finds nothing to claim."""
    job = s.get(Job, job_id)
    if job is None or job.status != "queued":
        return False
    job.status, job.updated_at = "running", _now()
    s.flush()
    return True


def set_password_hash(s: Session, *, user_id: str, password_hash: str) -> None:
    """Rehash on login with newer argon2 parameters (never a plaintext path)."""
    user = s.get(User, user_id)
    if user is None:
        raise ConflictError(f"no user {user_id}")
    user.password_hash = password_hash
    s.flush()


def add_chat_message(
    s: Session,
    *,
    tenant_id: str,
    case_id: str,
    user_id: str,
    role: str,
    redacted_text: str,
    intent: str | None,
    citations: list[str],
    trace_id: str,
) -> None:
    """Copilot memory (scope #2): the caller passes text already redacted (ONB-06, NFR-07)."""
    s.add(
        ChatMessage(
            tenant_id=tenant_id,
            case_id=case_id,
            user_id=user_id,
            role=role,
            redacted_text=redacted_text,
            intent=intent,
            citations_json=json.dumps(citations),
            trace_id=trace_id,
            created_at=_now(),
        )
    )


# ADR 0025: content tables a delete clears; ledger_facts, approvals and audit_log are append-only
# and stay. Children first (foreign keys are ON).
_CASE_CONTENT = (
    "chat_messages",
    "stage_runs",
    "jobs",
    "case_files",
)


def _rows(s: Session, sql: str, params: dict[str, str]) -> int:
    result: CursorResult[Any] = s.execute(text(sql), params)  # type: ignore[assignment]
    return int(result.rowcount)


def delete_case(
    s: Session, *, tenant_id: str, case_id: str, expected_version: int, actor: str
) -> dict[str, int]:
    """Scope #39, ADR 0025: remove the case content, keep the append-only record, leave a
    tombstone, append CASE_DELETED, and re-verify the chain before commit (fail closed)."""
    case = s.scalar(select(Case).where(Case.tenant_id == tenant_id, Case.id == case_id))
    if case is None or case.status == DELETED:
        raise ConflictError(f"no case {case_id}")
    if case.row_version != expected_version:
        raise ConflictError(f"case changed (version {case.row_version}, not {expected_version})")
    params = {"t": tenant_id, "c": case_id}
    removed: dict[str, int] = {}
    for table in _CASE_CONTENT:  # constant names; ids are bound parameters
        sql = f"DELETE FROM {table} WHERE tenant_id = :t AND case_id = :c"  # noqa: S608  # nosec B608
        removed[table] = _rows(s, sql, params)
    present = set(inspect(s.connection()).get_table_names())  # SQLite or MySQL (ADR 0039)
    for table in ("checkpoints", "writes"):  # LangGraph state for the case thread, if it ran
        if table in present:
            sql = f"DELETE FROM {table} WHERE thread_id = :th"  # noqa: S608  # nosec B608
            removed[table] = _rows(s, sql, {"th": f"{tenant_id}:{case_id}"})
    case.status, case.current_stage = DELETED, None
    case.msme_name = case.order_ref = "[deleted]"
    try:
        s.flush()
    except StaleDataError as exc:
        raise ConflictError("case changed concurrently") from exc
    append_audit(
        s,
        tenant_id=tenant_id,
        case_id=case_id,
        actor=actor,
        event_type="CASE_DELETED",
        payload={"case_version": expected_version, "removed": removed},
    )
    s.flush()
    if broken := verify_chain(s, tenant_id):
        raise ConflictError(f"audit chain broken at {broken[:5]}; nothing deleted")
    return removed
