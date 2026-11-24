"""Seeded generator for the 20 synthetic HR profiles (SQLite HR store), BRD v3.1 section 10.

Each profile is built deliberately for one scenario. The BRD's planted cases are all here:
expired training, missing record, wrong role and missing acknowledgement. The seed only
varies names and dates, so reruns give identical data.

    python -m readiness.generate_hr_data      # writes data/hr.db, data/hr_profiles.json, data/user_map.json
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from .rules import REQUIRED_ACKNOWLEDGEMENTS, REQUIRED_TRAININGS, TASK

SEED = 42
AS_OF = date(2026, 11, 2)          # reference date used by tests and the eval set
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

FIRST = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Ananya", "Vikram", "Isha", "Arjun", "Priya",
         "Nikhil", "Sneha", "Rahul", "Kavya", "Siddharth", "Neha", "Aditya", "Pooja", "Karan", "Riya"]
LAST = ["Sharma", "Iyer", "Reddy", "Nair", "Gupta", "Menon", "Rao", "Das", "Kulkarni", "Banerjee"]

# (employee_id, role, status, authorised?, overrides, expected decision, scenario)
# Training override per course code: "missing" | "in_progress" | "no_evidence" | "expired"
#                                    | "expires_today" | "expired_yesterday" | "future_date"
# Acknowledgement override, key "ACK_<policy code>": "missing" | "expired" | "no_evidence"
SCENARIOS = [
    ("EMP-001", "Finance Analyst",        "active", True,  {}, "GO", "Fully qualified"),
    ("EMP-002", "Senior Finance Analyst", "active", True,  {}, "GO", "Fully qualified (senior)"),
    ("EMP-003", "Relationship Manager",   "active", True,  {"ACK_POL_DATA": "expired"}, "NO_GO",
     "Data protection policy acknowledgement expired"),
    ("EMP-004", "Finance Manager",        "active", True,  {}, "GO", "Fully qualified (manager)"),
    ("EMP-005", "Finance Analyst",        "active", True,  {"COC": "expires_today"}, "GO",
     "Boundary: CoC valid through today"),
    ("EMP-006", "Relationship Manager",   "active", True,  {"ACK_POL_CREDIT": "missing"}, "NO_GO",
     "Credit policy never acknowledged (has an optional extra course too)"),
    ("EMP-007", "Finance Analyst",        "active", True,  {"FINDATA": "missing"}, "NO_GO",
     "Missing financial-data training"),
    ("EMP-008", "Finance Analyst",        "active", True,  {"WCPROC": "missing"}, "NO_GO",
     "Missing working-capital process training"),
    ("EMP-009", "Senior Finance Analyst", "active", True,  {"INFOSEC": "expired"}, "NO_GO",
     "InfoSec training expired"),
    ("EMP-010", "Finance Analyst",        "active", True,  {"COC": "expired_yesterday"}, "NO_GO",
     "Boundary: CoC expired yesterday"),
    ("EMP-011", "HR Executive",           "active", True,  {}, "NO_GO", "Role not authorised"),
    ("EMP-012", "Finance Analyst",        "exited", True,  {}, "NO_GO", "Employee has exited"),
    ("EMP-013", "Finance Analyst",        "active", False, {}, "NO_GO",
     "Task not authorised by manager"),
    ("EMP-014", "Relationship Manager",   "active", True,
     {"FINDATA": "missing", "WCPROC": "missing", "INFOSEC": "expired"}, "NO_GO", "Three blockers"),
    ("EMP-015", "Finance Analyst",        "active", True,  {"FINDATA": "no_evidence"}, "NEEDS_INPUT",
     "Marked completed but no evidence"),
    ("EMP-016", None,                     "active", True,  {}, "NEEDS_INPUT", "Role missing in HR record"),
    ("EMP-017", "Finance Analyst",        "active", True,  {"WCPROC": "in_progress"}, "NO_GO",
     "Training still in progress"),
    ("EMP-018", "Finance Analyst",        "active", True,
     {"FINDATA": "no_evidence", "INFOSEC": "expired"}, "NO_GO", "NO_GO outranks NEEDS_INPUT"),
    ("EMP-019", "Senior Finance Analyst", "on_leave", True, {}, "NO_GO", "Employee on leave"),
    ("EMP-020", "Finance Analyst",        "active", True,  {"INDUCTION": "future_date"}, "NEEDS_INPUT",
     "Completion date in the future (data error)"),
]


def _add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError(d)


def build_profiles(seed: int = SEED, as_of: date = AS_OF):
    """Returns (employees, training_records, acknowledgements, scenarios)."""
    rng = random.Random(seed)
    employees, records, acks, scenarios = [], [], [], []
    rec_no = ack_no = 0
    for idx, (emp_id, role, status, authorised, overrides, expected, label) in enumerate(SCENARIOS):
        employees.append({
            "employee_id": emp_id,
            "full_name": f"{FIRST[idx]} {rng.choice(LAST)}",
            "role": role,
            "department": "Finance" if role and "HR" not in role else ("Human Resources" if role else None),
            "manager_id": "EMP-100",
            "employment_status": status,
            "authorised_tasks": [TASK] if authorised else [],
        })
        scenarios.append({"employee_id": emp_id, "expected": expected, "scenario": label})

        courses = dict(REQUIRED_TRAININGS)
        if emp_id == "EMP-006":
            courses["EXCEL_ADV"] = ("Advanced Excel (optional)", None)
        for code, (name, months) in courses.items():
            mode = overrides.get(code)
            if mode == "missing":
                continue
            rec_no += 1
            completed = as_of - timedelta(days=rng.randint(30, 300))
            valid_until = _add_months(completed, months) if months else None
            rec = {
                "record_id": f"TR-{rec_no:04d}", "employee_id": emp_id, "course_code": code,
                "course_name": name, "status": "completed", "completed_on": completed.isoformat(),
                "valid_until": valid_until.isoformat() if valid_until else None,
                "evidence_id": f"LMS-{rng.randint(100000, 999999)}",
            }
            if mode == "in_progress":
                rec.update(status="in_progress", completed_on=None, valid_until=None, evidence_id=None)
            elif mode == "no_evidence":
                rec["evidence_id"] = None
            elif mode == "expired":
                old = as_of - timedelta(days=rng.randint(400, 500))
                rec.update(completed_on=old.isoformat(), valid_until=_add_months(old, months).isoformat())
            elif mode == "expires_today":
                rec.update(completed_on=_add_months(as_of, -months).isoformat(), valid_until=as_of.isoformat())
            elif mode == "expired_yesterday":
                y = as_of - timedelta(days=1)
                rec.update(completed_on=_add_months(y, -months).isoformat(), valid_until=y.isoformat())
            elif mode == "future_date":
                rec["completed_on"] = (as_of + timedelta(days=10)).isoformat()
            records.append(rec)

        for code, (name, months) in REQUIRED_ACKNOWLEDGEMENTS.items():
            mode = overrides.get(f"ACK_{code}")
            if mode == "missing":
                continue
            ack_no += 1
            on = as_of - timedelta(days=rng.randint(20, 200))
            ack = {"record_id": f"PA-{ack_no:04d}", "employee_id": emp_id, "policy_code": code,
                   "policy_name": name, "acknowledged_on": on.isoformat(),
                   "valid_until": _add_months(on, months).isoformat(),
                   "evidence_id": f"HRP-{rng.randint(100000, 999999)}"}
            if mode == "expired":
                old = as_of - timedelta(days=rng.randint(400, 450))
                ack.update(acknowledged_on=old.isoformat(), valid_until=_add_months(old, months).isoformat())
            elif mode == "no_evidence":
                ack["evidence_id"] = None
            acks.append(ack)
    return employees, records, acks, scenarios


def write_db(db_path: Path, employees: list[dict], records: list[dict], acks: list[dict] | None = None) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE employees (
            employee_id TEXT PRIMARY KEY, full_name TEXT NOT NULL, role TEXT, department TEXT,
            manager_id TEXT, employment_status TEXT NOT NULL, authorised_tasks TEXT NOT NULL);
        CREATE TABLE training_records (
            record_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(employee_id),
            course_code TEXT NOT NULL, course_name TEXT NOT NULL, status TEXT NOT NULL,
            completed_on TEXT, valid_until TEXT, evidence_id TEXT);
        CREATE TABLE policy_acknowledgements (
            record_id TEXT PRIMARY KEY, employee_id TEXT NOT NULL REFERENCES employees(employee_id),
            policy_code TEXT NOT NULL, policy_name TEXT NOT NULL, acknowledged_on TEXT,
            valid_until TEXT, evidence_id TEXT);
    """)
    con.executemany(
        "INSERT INTO employees VALUES (:employee_id,:full_name,:role,:department,:manager_id,"
        ":employment_status,:authorised_tasks)",
        [{**e, "authorised_tasks": json.dumps(e["authorised_tasks"])} for e in employees])
    con.executemany(
        "INSERT INTO training_records VALUES (:record_id,:employee_id,:course_code,:course_name,"
        ":status,:completed_on,:valid_until,:evidence_id)", records)
    con.executemany(
        "INSERT INTO policy_acknowledgements VALUES (:record_id,:employee_id,:policy_code,:policy_name,"
        ":acknowledged_on,:valid_until,:evidence_id)", acks or [])
    con.commit()
    con.close()


def hr_db_path() -> Path:
    """Where the HR store lives: CREDASSURE_HR_DB if set, else data/hr.db."""
    return Path(os.getenv("CREDASSURE_HR_DB", DATA_DIR / "hr.db"))


# Which UI login acts as which synthetic employee. The FinBridge UI's demo preparer maps to
# a fully qualified employee; edit data/user_map.json (or point CREDASSURE_USER_MAP at your
# own file) to try other profiles from the UI.
DEFAULT_USER_MAP = {"preparer@finbridge.demo": "EMP-001", "preparer": "EMP-001"}


def ensure_hr_store() -> None:
    """Create the HR store if it is missing, or rebuild it if it predates acknowledgements."""
    db = hr_db_path()
    if db.exists():
        with sqlite3.connect(db) as con:
            tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "policy_acknowledgements" in tables:
            return
    main()


def main() -> None:
    employees, records, acks, scenarios = build_profiles()
    db = hr_db_path()
    write_db(db, employees, records, acks)
    (db.parent / "hr_profiles.json").write_text(json.dumps(
        {"seed": SEED, "as_of": AS_OF.isoformat(), "employees": employees, "training_records": records,
         "policy_acknowledgements": acks, "scenarios": scenarios}, indent=2))
    user_map = db.parent / "user_map.json"
    if not user_map.exists():
        user_map.write_text(json.dumps(DEFAULT_USER_MAP, indent=2))
    print(f"Wrote {len(employees)} employees, {len(records)} training records and "
          f"{len(acks)} policy acknowledgements to {db}")


if __name__ == "__main__":
    main()
