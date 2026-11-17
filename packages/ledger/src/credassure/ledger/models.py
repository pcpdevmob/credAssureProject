"""SQLAlchemy models for case.db and corpus.db (design-detail §4).

Every case-scoped table carries tenant_id (scope #27). Money is integer paise or Decimal text,
never float (BR-05). cases and approvals carry row_version for optimistic concurrency (scope #49).
audit_log, ledger_facts and approvals are append-only: migration triggers abort UPDATE and DELETE.
hr.db is not modelled here: the generator writes it; runtime opens it read-only (session.hr_engine).
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

TENANT = String(64)


class CaseBase(DeclarativeBase):
    pass


class CorpusBase(DeclarativeBase):
    pass


class User(CaseBase):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(TENANT, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(32))
    emp_id: Mapped[str | None] = mapped_column(
        String(16)
    )  # S19 binding; never taken from chat (ONB-01)
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Case(CaseBase):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # CA-YYYY-NNNN
    tenant_id: Mapped[str] = mapped_column(TENANT, index=True)
    msme_name: Mapped[str] = mapped_column(String(200))
    order_ref: Mapped[str] = mapped_column(String(64))
    order_value_paise: Mapped[int] = mapped_column(BigInteger)
    indicative_amount_paise: Mapped[int] = mapped_column(
        BigInteger
    )  # UI-01: kept apart from any result
    due_date: Mapped[date] = mapped_column(Date)
    preparer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(32), default="CREATED")
    current_stage: Mapped[str | None] = mapped_column(String(32))
    route: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    row_version: Mapped[int] = mapped_column(Integer)
    __mapper_args__ = {"version_id_col": row_version}  # noqa: RUF012 - SQLAlchemy mapper config


class CaseFile(CaseBase):
    __tablename__ = "case_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(TENANT, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    schema_version: Mapped[str] = mapped_column(String(8))
    sha256: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class StageRun(CaseBase):
    __tablename__ = "stage_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(TENANT, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    stage: Mapped[str] = mapped_column(String(32))
    attempt: Mapped[int] = mapped_column(Integer)
    decision: Mapped[str | None] = mapped_column(String(16))
    result_json: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)


class LedgerFact(CaseBase):
    __tablename__ = "ledger_facts"
    __table_args__ = (UniqueConstraint("case_id", "key", "version"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(TENANT, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    key: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer)
    value_text: Mapped[str] = mapped_column(Text)  # Decimal/int as exact text
    unit: Mapped[str] = mapped_column(String(16))
    source_type: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str] = mapped_column(String(255))
    produced_by: Mapped[str] = mapped_column(String(128))  # engine/agent + version
    input_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class Approval(CaseBase):
    """Insert-only (APR-04). row_version = the case version the approver decided on (#49)."""

    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(TENANT, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(32))
    decision: Mapped[str] = mapped_column(String(16))  # approve | reject | return
    return_stage: Mapped[str | None] = mapped_column(String(32))
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime)
    row_version: Mapped[int] = mapped_column(Integer)


class AuditLog(CaseBase):
    """Append-only, hash-chained: hash = sha256(prev_hash || canonical JSON of the row)."""

    __tablename__ = "audit_log"
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    tenant_id: Mapped[str] = mapped_column(TENANT, index=True)
    case_id: Mapped[str | None] = mapped_column(String(16), index=True)
    actor: Mapped[str] = mapped_column(String(64))
    event_type: Mapped[str] = mapped_column(String(48))
    payload: Mapped[dict[str, Any]] = mapped_column("payload_json", JSON)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))
    ts: Mapped[str] = mapped_column(String(32))  # ISO-8601 UTC, hashed as text


class ChatMessage(CaseBase):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(TENANT, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    redacted_text: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(32))
    citations_json: Mapped[str] = mapped_column(Text, default="[]")
    trace_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)


class RunLock(CaseBase):
    """One active run per case (scope #22): a second insert for the same case fails."""

    __tablename__ = "run_locks"
    case_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(TENANT)
    run_id: Mapped[str] = mapped_column(String(64))
    acquired_at: Mapped[datetime] = mapped_column(DateTime)


class AuditHead(CaseBase):
    """Newest (seq, hash) of the audit chain, written with every append: a cut tail no longer
    matches it (OBJ-08). Mutable by design, so it carries no append-only trigger."""

    __tablename__ = "audit_head"
    tenant_id: Mapped[str] = mapped_column(TENANT, primary_key=True)
    seq: Mapped[int] = mapped_column(Integer)
    hash: Mapped[str] = mapped_column(String(64))


class Job(CaseBase):
    """Asynchronous run of the workflow or one stage (ADR 0007, scope #47)."""

    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("tenant_id", "case_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(TENANT, index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # run | stage | decision
    stage: Mapped[str | None] = mapped_column(String(32))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))  # queued|running|succeeded|failed|abandoned
    outcome: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class AppConfig(CaseBase):
    __tablename__ = "app_config"
    tenant_id: Mapped[str] = mapped_column(TENANT, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class PromptRegistry(CaseBase):
    __tablename__ = "prompt_registry"
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(16), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)


class EvalRun(CaseBase):
    __tablename__ = "eval_runs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    config_json: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class EvalResult(CaseBase):
    __tablename__ = "eval_results"
    run_id: Mapped[str] = mapped_column(ForeignKey("eval_runs.id"), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    category: Mapped[str] = mapped_column(String(32))
    passed: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[str | None] = mapped_column(String(16))
    failure_class: Mapped[str | None] = mapped_column(String(32))
    trace_id: Mapped[str | None] = mapped_column(String(64))
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)


# corpus.db (filled by `make ingest`, Phase 7)
class Document(CorpusBase):
    __tablename__ = "documents"
    doc_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(String(128))
    collection: Mapped[str] = mapped_column(String(32))  # public | policy | kfs | faq
    jurisdiction: Mapped[str] = mapped_column(String(8), default="IN")
    applies_to: Mapped[str] = mapped_column(String(64), default="all")  # ADR 0019
    effective_from: Mapped[date | None] = mapped_column(Date)
    superseded_by: Mapped[str | None] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64))
    license_note: Mapped[str | None] = mapped_column(Text)
    case_id: Mapped[str | None] = mapped_column(String(16), index=True)  # KFS only
    legal_basis: Mapped[str | None] = mapped_column(String(4))  # L1-L5 (ADR 0019)
    tenant_id: Mapped[str | None] = mapped_column(String(64))  # with case_id: KFS of that case only
    # text sha256 : chunker version : embed model; ingest skips a document whose key is unchanged
    index_version: Mapped[str | None] = mapped_column(String(160))


class Chunk(CorpusBase):
    __tablename__ = "chunks"
    chunk_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    doc_id: Mapped[str] = mapped_column(ForeignKey("documents.doc_id"), index=True)
    strategy: Mapped[str] = mapped_column(String(16))  # fixed512 | section | semantic
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    section_path: Mapped[str | None] = mapped_column(Text)
    injection_flag: Mapped[bool] = mapped_column(Boolean, default=False)
