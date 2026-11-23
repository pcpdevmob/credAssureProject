"""Minimal `cases` table helpers used by the readiness endpoints.

The Supervisor owner owns the real cases API (BRD 6.1, POST /cases). These helpers only do
what Gate 1 needs: find a case, read its preparer, and record its readiness_status. If the
team's backend already has equivalents, swap them in here; nothing else changes.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .audit import db_path

DEMO_CASES = [
    # Fictional companies only. One GO and two blocked cases, for demos (NFR-08).
    {"case_id": "CASE-001", "customer_name": "Suryodaya Circuits Pvt Ltd (fictional)",
     "requested_amount": "20000000", "currency": "INR", "preparer_id": "EMP-001"},
    {"case_id": "CASE-002", "customer_name": "Nilgiri Components LLP (fictional)",
     "requested_amount": "12500000", "currency": "INR", "preparer_id": "EMP-007"},
    {"case_id": "CASE-003", "customer_name": "Deccan Power Electronics (fictional)",
     "requested_amount": "16000000", "currency": "INR", "preparer_id": "EMP-006"},
]


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS cases (
        case_id TEXT PRIMARY KEY, customer_name TEXT NOT NULL, requested_amount TEXT NOT NULL,
        currency TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL,
        readiness_status TEXT NOT NULL DEFAULT 'NOT_CHECKED')""")
    # The team's own cases table may predate Gate 1: add the columns it needs.
    cols = {r["name"] for r in con.execute("PRAGMA table_info(cases)")}
    if "readiness_status" not in cols:
        con.execute("ALTER TABLE cases ADD COLUMN readiness_status TEXT NOT NULL DEFAULT 'NOT_CHECKED'")
    if "preparer_id" not in cols:
        con.execute("ALTER TABLE cases ADD COLUMN preparer_id TEXT")
    return con


def seed_demo_cases() -> None:
    """Insert the demo cases only if they are not already present."""
    with _connect() as con:
        for c in DEMO_CASES:
            con.execute("INSERT OR IGNORE INTO cases (case_id, customer_name, requested_amount, currency, "
                        "status, created_at, preparer_id) VALUES (?,?,?,?,?,?,?)",
                        (c["case_id"], c["customer_name"], c["requested_amount"], c["currency"],
                         "OPEN", datetime.now(timezone.utc).isoformat(), c["preparer_id"]))


def get_case(case_id: str) -> Optional[dict]:
    with _connect() as con:
        row = con.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    return dict(row) if row else None


def list_cases() -> list[dict]:
    with _connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM cases ORDER BY case_id").fetchall()]


def set_readiness_status(case_id: str, status: str) -> None:
    with _connect() as con:
        con.execute("UPDATE cases SET readiness_status = ? WHERE case_id = ?", (status, case_id))
