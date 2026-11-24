"""The Onboarding Agent's three tools: deterministic and read-only (BRD ONB-01, ONB-05).

They read only the synthetic HR store, a separate SQLite file opened read-only, so no
tool can write HR data or mark training complete. They never read case data (BR-14),
and values never come from chat.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

from .schemas import Employee, PolicyAcknowledgement, TrainingRecord

DEFAULT_HR_DB = Path(__file__).resolve().parent.parent / "data" / "hr.db"


class HRStoreUnavailable(RuntimeError):
    pass


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(db_path or os.getenv("CREDASSURE_HR_DB", DEFAULT_HR_DB))
    if not path.exists():
        raise HRStoreUnavailable(f"HR store not found at {path}")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)   # read-only
    con.row_factory = sqlite3.Row
    return con


def get_employee_record(employee_id: str, db_path: Optional[Path] = None) -> Optional[Employee]:
    """Return the employee's HR record, or None if the ID is not in the HR system."""
    with _connect(db_path) as con:
        row = con.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,)).fetchone()
    if row is None:
        return None
    data = dict(row)
    data["authorised_tasks"] = json.loads(data["authorised_tasks"])
    return Employee(**data)


def get_training_status(employee_id: str, db_path: Optional[Path] = None) -> list[TrainingRecord]:
    """Return every training record held for the employee (may be empty)."""
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM training_records WHERE employee_id = ? ORDER BY course_code",
            (employee_id,)).fetchall()
    return [TrainingRecord(**dict(r)) for r in rows]


def get_policy_acknowledgements(employee_id: str, db_path: Optional[Path] = None) -> list[PolicyAcknowledgement]:
    """Return every policy acknowledgement held for the employee (may be empty)."""
    try:
        with _connect(db_path) as con:
            rows = con.execute(
                "SELECT * FROM policy_acknowledgements WHERE employee_id = ? ORDER BY policy_code",
                (employee_id,)).fetchall()
    except sqlite3.OperationalError as exc:
        raise HRStoreUnavailable(f"{exc}: regenerate the HR store with python -m readiness.generate_hr_data")
    return [PolicyAcknowledgement(**dict(r)) for r in rows]
