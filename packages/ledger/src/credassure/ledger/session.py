"""Engines and transactions for case.db / corpus.db, the run lock, and the read-only hr.db engine.

Scope #22: WAL, busy_timeout 5000 ms, foreign keys on, and every transaction starts with
BEGIN IMMEDIATE so writers queue on the busy timeout instead of failing mid-transaction.

ADR 0039: case.db may instead be a MySQL 8 database (``CASE_DATABASE_URL=mysql+pymysql://...``).
The same guarantee is kept: every transaction first locks the single ``write_lock`` row
(``SELECT ... FOR UPDATE``), so writers queue exactly as under BEGIN IMMEDIATE and every invariant
that relies on it (audit seq = max + 1, case id allocation, last admin, code spend, job claim, run
lock) holds unchanged. READ COMMITTED lets each statement see rows committed by the writer before.
Migrations skip the lock (the table may not exist yet) with the ``no_write_lock`` option.
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from sqlalchemy import CursorResult, Engine, create_engine, delete, event, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .models import RunLock

BUSY_TIMEOUT_MS = 5000
HEARTBEAT = timedelta(seconds=30)  # a live run refreshes its lock this often (ADR 0007)
STALE_LOCK = 3 * HEARTBEAT  # three missed heartbeats: the run is dead and its lock may be taken


MYSQL_COLLATION = "utf8mb4_bin"  # case-sensitive, byte-exact like SQLite (ids, usernames, keys)
NO_WRITE_LOCK = "no_write_lock"  # execution option: migrations run before write_lock exists


class RunInProgressError(Exception):
    """A run already holds this case (scope #22): the API answers 409."""


class DatabaseConfigError(RuntimeError):
    """The configured MySQL database cannot give SQLite's guarantees (ADR 0039)."""


def is_url(target: Path | str) -> bool:
    """A database URL (MySQL, ADR 0039) rather than a SQLite file path."""
    return "://" in str(target)


def case_engine(target: Path | str) -> Engine:
    """Engine for case.db (SQLite path or MySQL URL) or corpus.db with the scope #22 guarantees."""
    if is_url(target):
        return _mysql_engine(str(target))
    engine = create_engine(f"sqlite:///{target}")

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


def _mysql_engine(url: str) -> Engine:
    u = make_url(url)
    if u.get_backend_name() != "mysql":
        raise DatabaseConfigError(f"unsupported database {u.get_backend_name()!r}: use mysql")
    u = u.update_query_dict({"charset": "utf8mb4"})
    engine = create_engine(
        u, pool_pre_ping=True, pool_recycle=1800, isolation_level="READ COMMITTED"
    )

    @event.listens_for(engine, "connect")
    def _session(con: Any, _record: Any) -> None:
        cur = con.cursor()
        cur.execute("SET time_zone = '+00:00'")  # naive DATETIMEs are UTC, as in SQLite
        cur.execute("SET SESSION innodb_lock_wait_timeout = 30")
        cur.execute("SELECT @@collation_database")
        (collation,) = cur.fetchone()
        cur.close()
        if collation != MYSQL_COLLATION:
            raise DatabaseConfigError(
                f"database collation is {collation}; create it with "
                f"CHARACTER SET utf8mb4 COLLATE {MYSQL_COLLATION} (ADR 0039)"
            )

    @event.listens_for(engine, "begin")
    def _begin(conn: Any) -> None:
        if not conn.get_execution_options().get(NO_WRITE_LOCK):
            conn.execute(text("SELECT id FROM write_lock WHERE id = 1 FOR UPDATE"))

    return engine


@contextmanager
def transaction(engine: Engine) -> Iterator[Session]:
    """Unit of work: commit on success, roll back everything (facts and their audit) on error."""
    with sessionmaker(engine, expire_on_commit=False).begin() as session:
        yield session


@contextmanager
def run_lock(engine: Engine, tenant_id: str, case_id: str, run_id: str) -> Iterator[None]:
    """One active run per case. A lock not refreshed for STALE_LOCK (dead run) is taken over."""
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


def run_in_progress(engine: Engine, case_id: str) -> bool:
    """A live (not stale) run lock exists: callers answer 409 RUN_IN_PROGRESS (ADR 0007)."""
    cutoff = datetime.now(UTC) - STALE_LOCK
    with transaction(engine) as s:
        held = select(RunLock.case_id).where(
            RunLock.case_id == case_id, RunLock.acquired_at >= cutoff
        )
        return s.scalar(held) is not None


def heartbeat(engine: Engine, case_id: str, run_id: str) -> bool:
    """Refresh this run's lock. False means another run took it over: stop writing."""
    with transaction(engine) as s:
        result = s.execute(
            update(RunLock)
            .where(RunLock.case_id == case_id, RunLock.run_id == run_id)
            .values(acquired_at=datetime.now(UTC))
        )
        return bool(cast(CursorResult[Any], result).rowcount)


def hr_engine(path: Path | str) -> Engine:
    """hr.db opened read-only at the SQLite level (ONB-05): no write path exists at runtime."""
    uri = Path(path).resolve().as_uri() + "?mode=ro"  # escapes ? and # in the path

    def connect() -> sqlite3.Connection:
        con = sqlite3.connect(uri, uri=True, check_same_thread=False)
        con.execute("PRAGMA query_only=ON")
        return con

    return create_engine("sqlite://", creator=connect)
