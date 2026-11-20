"""ADR 0039: case.db on SQLite or MySQL keeps the same guarantees. Run with
CREDASSURE_TEST_MYSQL_URL set to test MySQL; without it these run on SQLite."""

import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from credassure.ledger import migrate, reads, session, writes
from credassure.ledger.models import AuditLog, RunLock

T = "default"


def test_ADR0039_concurrent_writers_keep_one_unbroken_audit_chain(
    case_target: Path | str,
) -> None:
    """Eight threads append at once: seq stays 1..n with no gap or duplicate and the chain verifies
    (SQLite: BEGIN IMMEDIATE; MySQL: every transaction locks the write_lock row first)."""
    migrate.upgrade("case", case_target)
    engine = session.case_engine(case_target)
    errors: list[BaseException] = []

    def worker(n: int) -> None:
        try:
            for i in range(10):
                with session.transaction(engine) as s:
                    writes.append_audit(
                        s,
                        tenant_id=T,
                        case_id=None,
                        actor=f"t{n}",
                        event_type="TEST",
                        payload={"n": n, "i": i},
                    )
        except BaseException as exc:  # surfaced by the assert below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    with session.transaction(engine) as s:
        seqs = list(s.scalars(select(AuditLog.seq).order_by(AuditLog.seq)))
        assert seqs == list(range(1, 81))
        assert reads.verify_chain(s) == []
    engine.dispose()


def test_ADR0039_timestamps_keep_microseconds(case_target: Path | str) -> None:
    """The audit hash covers `ts`: a DATETIME without fractions would break verification."""
    migrate.upgrade("case", case_target)
    engine = session.case_engine(case_target)
    at = datetime(2026, 11, 20, 10, 11, 12, 345678, tzinfo=UTC)
    with session.transaction(engine) as s:
        s.add(RunLock(case_id="CA-2026-0001", tenant_id=T, run_id="r", acquired_at=at))
    with session.transaction(engine) as s:
        got = s.scalar(select(RunLock.acquired_at))
    assert got is not None and got.replace(tzinfo=UTC) == at
    engine.dispose()


def test_ADR0039_case_and_username_are_case_sensitive(case_target: Path | str) -> None:
    """utf8mb4_bin, like SQLite: 'Prep' and 'prep' are two usernames, never one."""
    migrate.upgrade("case", case_target)
    engine = session.case_engine(case_target)
    with session.transaction(engine) as s:
        for uid, name in (("u1", "prep"), ("u2", "Prep")):
            writes.add_user(
                s, user_id=uid, tenant_id=T, username=name, role="preparer", password_hash="x"
            )
    with session.transaction(engine) as s:
        lower, upper = reads.user_by_name(s, "prep"), reads.user_by_name(s, "Prep")
    engine.dispose()
    assert lower is not None and lower.id == "u1"
    assert upper is not None and upper.id == "u2"


def test_ADR0039_unsupported_url_and_corpus_on_mysql_are_refused() -> None:
    with pytest.raises(session.DatabaseConfigError):
        session.case_engine("postgresql://u:p@h/db")
    with pytest.raises(ValueError, match="FTS5"):
        migrate.upgrade("corpus", "mysql+pymysql://u:p@h/db")
