"""Engines and transactions for case.db / corpus.db, the run lock, and the read-only hr.db engine.

Scope #22: WAL, busy_timeout 5000 ms, foreign keys on, and every transaction starts with
BEGIN IMMEDIATE so writers queue on the busy timeout instead of failing mid-transaction.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from sqlalchemy import CursorResult, Engine, create_engine, delete, event, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .models import RunLock

BUSY_TIMEOUT_MS = 5000
STALE_LOCK = timedelta(minutes=5)  # the stage timeout (#23): an older lock belongs to a dead run


class RunInProgressError(Exception):
    """A run already holds this case (scope #22): the API answers 409."""


def case_engine(path: Path | str) -> Engine:
    """Engine for case.db or corpus.db with the scope #22 pragmas."""
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def _pragmas(con: Any, _record: Any) -> None:
        con.isolation_level = None  # SQLAlchemy emits BEGIN itself (below)
        cur = con.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    @event.listens_for(engine, "begin")
    def _begin(conn: Any) -> None:
        # ponytail: every transaction takes the write lock up front; split read/write engines if
        # read concurrency ever matters (one gateway process, capped harness concurrency today).
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


@contextmanager
def transaction(engine: Engine) -> Iterator[Session]:
    """Unit of work: commit on success, roll back everything (facts and their audit) on error."""
    with sessionmaker(engine, expire_on_commit=False).begin() as session:
        yield session


@contextmanager
def run_lock(engine: Engine, tenant_id: str, case_id: str, run_id: str) -> Iterator[None]:
    """One active run per case. A lock older than STALE_LOCK (crashed run) is taken over."""
    now = datetime.now(UTC)
    try:
        with transaction(engine) as s:
            s.add(RunLock(case_id=case_id, tenant_id=tenant_id, run_id=run_id, acquired_at=now))
    except IntegrityError as exc:
        with transaction(engine) as s:
            result = s.execute(
                update(RunLock)
                .where(RunLock.case_id == case_id, RunLock.acquired_at < now - STALE_LOCK)
                .values(run_id=run_id, tenant_id=tenant_id, acquired_at=now)
            )
            stolen = cast(CursorResult[Any], result).rowcount  # UPDATE returns a CursorResult
        if not stolen:
            raise RunInProgressError(case_id) from exc
    try:
        yield
    finally:
        with transaction(engine) as s:
            s.execute(delete(RunLock).where(RunLock.case_id == case_id, RunLock.run_id == run_id))


def hr_engine(path: Path | str) -> Engine:
    """hr.db opened read-only at the SQLite level (ONB-05): no write path exists at runtime."""
    uri = Path(path).resolve().as_uri() + "?mode=ro"  # escapes ? and # in the path

    def connect() -> sqlite3.Connection:
        con = sqlite3.connect(uri, uri=True, check_same_thread=False)
        con.execute("PRAGMA query_only=ON")
        return con

    return create_engine("sqlite://", creator=connect)
