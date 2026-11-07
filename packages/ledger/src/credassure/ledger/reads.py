"""Tenant- and case-scoped reads (SUP-08, scope #27) and audit-chain verification (OBJ-08)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from .chain import GENESIS, hashed_fields, row_hash
from .models import AuditHead, AuditLog, Case, LedgerFact


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


def audit_head(s: Session, tenant_id: str) -> AuditHead | None:
    return s.get(AuditHead, tenant_id)


def verify_chain(s: Session) -> list[int]:
    """Seq numbers whose link is broken (edited row, wrong prev_hash, gap). Empty = intact.

    Each tenant's newest row must also match its audit_head anchor, so cutting off the newest
    rows is caught (OBJ-08). ponytail: whoever can rewrite the file can rewrite the anchor too;
    export heads to traces or HMAC the chain with an env key if that threat matters.
    """
    broken, prev, expected_seq = [], GENESIS, 1
    tail: dict[str, AuditLog] = {}
    for row in s.scalars(select(AuditLog).order_by(AuditLog.seq)):
        tail[row.tenant_id] = row
        fields = hashed_fields(
            row.seq, row.tenant_id, row.case_id, row.actor, row.event_type, row.payload, row.ts
        )
        if row.seq != expected_seq or row.prev_hash != prev or row.hash != row_hash(prev, fields):
            broken.append(row.seq)
        prev, expected_seq = row.hash, row.seq + 1
    for head in s.scalars(select(AuditHead)):
        last = tail.get(head.tenant_id)
        if last is None or last.seq != head.seq or last.hash != head.hash:
            broken.append(head.seq)
    return broken
