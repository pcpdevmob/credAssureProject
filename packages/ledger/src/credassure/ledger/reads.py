"""Tenant- and case-scoped reads (SUP-08, scope #27) and audit-chain verification (OBJ-08)."""

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .chain import GENESIS, hashed_fields, row_hash
from .models import (
    AppConfig,
    Approval,
    AuditHead,
    AuditLog,
    Case,
    CaseFile,
    ChatMessage,
    Chunk,
    Document,
    Job,
    LedgerFact,
    StageRun,
    User,
)

DELETED = "DELETED"  # ADR 0025 tombstone status


def get_case(s: Session, tenant_id: str, case_id: str) -> Case | None:
    return s.scalar(select(Case).where(Case.tenant_id == tenant_id, Case.id == case_id))


def get_latest(s: Session, tenant_id: str, case_id: str, key: str) -> LedgerFact | None:
    return s.scalar(
        select(LedgerFact)
        .where(
            LedgerFact.tenant_id == tenant_id, LedgerFact.case_id == case_id, LedgerFact.key == key
        )
        .order_by(LedgerFact.version.desc())
        .limit(1)
    )


def list_for_case(s: Session, tenant_id: str, case_id: str) -> list[LedgerFact]:
    """Every version of every fact for one case, by key then version."""
    return list(
        s.scalars(
            select(LedgerFact)
            .where(LedgerFact.tenant_id == tenant_id, LedgerFact.case_id == case_id)
            .order_by(LedgerFact.key, LedgerFact.version)
        )
    )


def audit_events(s: Session, tenant_id: str, case_id: str) -> list[AuditLog]:
    return list(
        s.scalars(
            select(AuditLog)
            .where(AuditLog.tenant_id == tenant_id, AuditLog.case_id == case_id)
            .order_by(AuditLog.seq)
        )
    )


def notice_acknowledged(s: Session, tenant_id: str, user_id: str, version: str) -> str | None:
    """Scope #40: when this user acknowledged this notice version (ISO time), if ever."""
    for event in s.scalars(
        select(AuditLog)
        .where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.event_type == "CHAT_NOTICE_ACKNOWLEDGED",
            AuditLog.actor == user_id,
        )
        .order_by(AuditLog.seq)
    ):
        if event.payload.get("version") == version:
            return event.ts
    return None


def audit_head(s: Session, tenant_id: str) -> AuditHead | None:
    return s.get(AuditHead, tenant_id)


def verify_chain(s: Session, tenant_id: str | None = None) -> list[int]:
    """Seq numbers whose link is broken (edited row, wrong prev_hash, gap). Empty = intact.

    Each tenant's newest row must also match its audit_head anchor, so cutting off the newest
    rows is caught (OBJ-08). The chain is global; ``tenant_id`` reports only that tenant's
    broken seqs, so one tenant never sees another's (E10 SHOULD-3).
    ponytail: whoever can rewrite the file can rewrite the anchor too;
    export heads to traces or HMAC the chain with an env key if that threat matters.
    """
    broken: list[tuple[int, str]] = []
    prev, expected_seq = GENESIS, 1
    tail: dict[str, AuditLog] = {}
    for row in s.scalars(select(AuditLog).order_by(AuditLog.seq)):
        tail[row.tenant_id] = row
        fields = hashed_fields(
            row.seq, row.tenant_id, row.case_id, row.actor, row.event_type, row.payload, row.ts
        )
        if row.seq != expected_seq or row.prev_hash != prev or row.hash != row_hash(prev, fields):
            broken.append((row.seq, row.tenant_id))
        prev, expected_seq = row.hash, row.seq + 1
    for head in s.scalars(select(AuditHead)):
        last = tail.get(head.tenant_id)
        if last is None or last.seq != head.seq or last.hash != head.hash:
            broken.append((head.seq, head.tenant_id))
    return [seq for seq, owner in broken if tenant_id in (None, owner)]


def get_user(s: Session, user_id: str) -> User | None:
    return s.get(User, user_id)


def preparer_emp_id(s: Session, tenant_id: str, case_id: str) -> str | None:
    """The case preparer's HR id, from the login binding, never from chat (ONB-01, SUP-08)."""
    return s.scalar(
        select(User.emp_id)
        .join(Case, Case.preparer_id == User.id)
        .where(
            Case.tenant_id == tenant_id,
            Case.id == case_id,
            User.tenant_id == tenant_id,
            User.active.is_(True),
        )
    )


def user_by_name(s: Session, username: str) -> User | None:
    return s.scalar(select(User).where(User.username == username))


def list_cases(s: Session, tenant_id: str) -> list[Case]:
    """Live cases only: a DELETED tombstone (ADR 0025) is never listed."""
    return list(
        s.scalars(
            select(Case)
            .where(Case.tenant_id == tenant_id, Case.status != DELETED)
            .order_by(Case.id)
        )
    )


def stage_runs(s: Session, tenant_id: str, case_id: str) -> list[StageRun]:
    return list(
        s.scalars(
            select(StageRun)
            .where(StageRun.tenant_id == tenant_id, StageRun.case_id == case_id)
            .order_by(StageRun.id)
        )
    )


def case_files(s: Session, tenant_id: str, case_id: str) -> list[CaseFile]:
    return list(
        s.scalars(
            select(CaseFile)
            .where(CaseFile.tenant_id == tenant_id, CaseFile.case_id == case_id)
            .order_by(CaseFile.id)
        )
    )


def get_job(s: Session, tenant_id: str, job_id: str) -> Job | None:
    job = s.get(Job, job_id)
    return job if job is not None and job.tenant_id == tenant_id else None


def get_config(s: Session, tenant_id: str, key: str) -> str | None:
    row = s.get(AppConfig, (tenant_id, key))
    return None if row is None else row.value


def tokens_used(s: Session, tenant_id: str) -> int:
    """Quota usage (scope #16): tokens recorded on every finished stage run."""
    total = s.scalar(
        select(
            func.coalesce(func.sum(func.json_extract(StageRun.result_json, "$.tokens_used")), 0)
        ).where(StageRun.tenant_id == tenant_id)
    )
    return int(total or 0)


def approvals(s: Session, tenant_id: str, case_id: str) -> list[Approval]:
    return list(
        s.scalars(
            select(Approval)
            .where(Approval.tenant_id == tenant_id, Approval.case_id == case_id)
            .order_by(Approval.id)
        )
    )


def job_by_key(s: Session, tenant_id: str, case_id: str, key: str) -> Job | None:
    return s.scalar(
        select(Job).where(
            Job.tenant_id == tenant_id, Job.case_id == case_id, Job.idempotency_key == key
        )
    )


def get_fact(
    s: Session, tenant_id: str, case_id: str, key: str, version: int | None = None
) -> LedgerFact | None:
    """One version of a fact (latest when version is None) — lineage (#33)."""
    if version is None:
        return get_latest(s, tenant_id, case_id, key)
    return s.scalar(
        select(LedgerFact).where(
            LedgerFact.tenant_id == tenant_id,
            LedgerFact.case_id == case_id,
            LedgerFact.key == key,
            LedgerFact.version == version,
        )
    )


def fact_event(s: Session, tenant_id: str, case_id: str, key: str, version: int) -> AuditLog | None:
    """The FACT_WRITTEN event of one fact version (actor, time, agent, stage, trace)."""
    events = s.scalars(
        select(AuditLog)
        .where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.case_id == case_id,
            AuditLog.event_type == "FACT_WRITTEN",
        )
        .order_by(AuditLog.seq.desc())
    )
    # ponytail: scans the case's FACT_WRITTEN events in Python (JSON payload, no index);
    # add a (case_id, key, version) column on audit_log if a case ever holds many thousands.
    return next(
        (e for e in events if e.payload.get("key") == key and e.payload.get("version") == version),
        None,
    )


def corpus_refs(
    s: Session, ids: list[str], tenant_id: str, case_id: str, own_kfs: frozenset[str] = frozenset()
) -> dict[str, tuple[str, str, str | None, str | None]]:
    """id -> (doc_id, title, section, chunk_id) for corpus chunk or document ids; another
    case's KFS never resolves (SUP-08), except a KFS this case uploaded (``own_kfs``:
    "doc_id@sha256", the retrieval rule)."""
    out: dict[str, tuple[str, str, str | None, str | None]] = {}
    visible = (
        Document.case_id.is_(None)
        | ((Document.case_id == case_id) & (Document.tenant_id == tenant_id))
        | (
            (Document.collection == "kfs")
            & (Document.doc_id + "@" + Document.sha256).in_(own_kfs)
            & (Document.tenant_id.is_(None) | (Document.tenant_id == tenant_id))
        )
    )
    for chunk, doc in s.execute(
        select(Chunk, Document).join(Document).where(Chunk.chunk_id.in_(ids), visible)
    ):
        out[chunk.chunk_id] = (doc.doc_id, doc.title, chunk.section_path, chunk.chunk_id)
    for doc in s.scalars(select(Document).where(Document.doc_id.in_(ids), visible)):
        out[doc.doc_id] = (doc.doc_id, doc.title, None, None)
    return out


def chat_history(
    s: Session, tenant_id: str, case_id: str, user_id: str, n: int
) -> list[ChatMessage]:
    """The last ``n`` redacted messages of this user in this case since their last reset, oldest
    first (scope #2, CP-11). Keyed by (tenant, case, user): memory never crosses cases or people.
    A reset is a stored marker row (role ``reset``); nothing before it is returned."""
    if n <= 0:
        return []
    scope = (
        ChatMessage.tenant_id == tenant_id,
        ChatMessage.case_id == case_id,
        ChatMessage.user_id == user_id,
    )
    last_reset = s.scalar(
        select(func.max(ChatMessage.id)).where(*scope, ChatMessage.role == "reset")
    )
    rows = s.scalars(
        select(ChatMessage)
        .where(*scope, ChatMessage.id > (last_reset or 0), ChatMessage.role != "reset")
        .order_by(ChatMessage.id.desc())
        .limit(n)
    )
    return list(reversed(list(rows)))


def feedback_given(s: Session, tenant_id: str, user_id: str, trace_id: str) -> bool:
    """CP-12: has this user already rated the answer ``trace_id``? (one rating per answer)"""
    return (
        s.scalar(
            select(AuditLog.seq)
            .where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.actor == user_id,
                AuditLog.event_type == "COPILOT_FEEDBACK",
                func.json_extract(AuditLog.payload, "$.trace_id") == trace_id,
            )
            .limit(1)
        )
        is not None
    )


def chat_turn_by_trace(
    s: Session, tenant_id: str, user_id: str, trace_id: str
) -> ChatMessage | None:
    """CP-12: this user's stored answer with ``trace_id`` (never another person's)."""
    return s.scalar(
        select(ChatMessage).where(
            ChatMessage.tenant_id == tenant_id,
            ChatMessage.user_id == user_id,
            ChatMessage.trace_id == trace_id,
            ChatMessage.role == "assistant",
        )
    )


def own_kfs(s: Session, tenant_id: str, case_id: str) -> frozenset[str]:
    """ "doc_id@sha256" of every KFS uploaded to this case: the corpus KFS it may read (9e).
    The sha is of the uploaded bytes, the same hash the corpus records for the synthetic KFS."""
    rows = s.scalars(
        select(CaseFile).where(
            CaseFile.tenant_id == tenant_id, CaseFile.case_id == case_id, CaseFile.kind == "kfs"
        )
    )
    out = set()
    for f in rows:
        doc = json.loads(f.payload_json).get("doc_id")
        if isinstance(doc, str) and doc:
            out.add(f"{doc}@{f.sha256}")
    return frozenset(out)
