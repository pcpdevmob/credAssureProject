"""Append-only audit log (`audit_events`) and optional Langfuse tracing (BRD OBJ-08, section 14).

Writes to the shared case database (CREDASSURE_DB, default data/credassure.db).
Only IDs, decisions and blocker codes are logged: no document contents, no keys.
When the integration owner's audit helper exists, replace `audit_event` with it.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "credassure.db"


def db_path() -> Path:
    return Path(os.getenv("CREDASSURE_DB", DEFAULT_DB))


def ensure_audit_table(con: sqlite3.Connection) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS audit_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT NOT NULL,
        actor_role TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL,
        details TEXT NOT NULL, created_at TEXT NOT NULL)""")
    con.execute("""CREATE TRIGGER IF NOT EXISTS audit_events_no_update BEFORE UPDATE ON audit_events
        BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END""")
    con.execute("""CREATE TRIGGER IF NOT EXISTS audit_events_no_delete BEFORE DELETE ON audit_events
        BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END""")


def audit_event(case_id: str, actor_role: str, action: str, status: str, details: dict) -> int:
    """Append one event and return its event_id."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as con:
        ensure_audit_table(con)
        cur = con.execute("INSERT INTO audit_events (case_id, actor_role, action, status, details, created_at) "
                          "VALUES (?,?,?,?,?,?)",
                          (case_id, actor_role, action, status, json.dumps(details, default=str),
                           datetime.now(timezone.utc).isoformat()))
        return int(cur.lastrowid)


def observe(name: str):
    """Langfuse @observe if available and configured, otherwise a no-op decorator."""
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        try:
            from langfuse import observe as lf_observe          # Langfuse v3
        except ImportError:
            try:
                from langfuse.decorators import observe as lf_observe   # Langfuse v2
            except ImportError:
                lf_observe = None
        if lf_observe:
            return lf_observe(name=name)
    return lambda fn: fn
