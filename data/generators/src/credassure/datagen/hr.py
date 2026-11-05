"""S01 HR store (DATA_SPEC §1) and S19 login bindings (DATA_SPEC §8.2).

Parameters:
- Roles: credit_proposal_officer and senior_finance_analyst may prepare; finance_analyst and
  accounts_executive may not (team-defined rule set, BRD Q-03).
- Mandatory trainings per authorised role: FIN-101 (12 months), AML-201 (12 months, basis R-RBI-09),
  DPDP-101 (24 months, basis R-DPDP-01). Policy acknowledgement: WC-POL v3.
- Display names are obviously fictional; no Aadhaar, PAN or account number anywhere.

Writes ``hr/profiles.json`` (frozen, hashed) and builds ``hr.db`` from it (gitignored, rebuilt by
``make data``; opened read-only at runtime, ONB-05).
"""

import sqlite3
from datetime import date, timedelta
from typing import Any

from credassure.core.schemas.hr import HrProfile, TrainingRecord

from .common import AS_OF_DATE, OUT, add_months, rng, write_json, write_yaml

AUTHORISED = ("credit_proposal_officer", "senior_finance_analyst")
UNAUTHORISED = ("finance_analyst", "accounts_executive")
TRAININGS = {
    "FIN-101": ("Credit Policy", 12),
    "AML-201": ("AML/KYC", 12),
    "DPDP-101": ("Data Protection", 24),
}
POLICY_ID, POLICY_VERSION = "WC-POL", "v3"

# (plant, count) in the order of DATA_SPEC §1. The plant names are reused in PLANTS.md.
PLAN = [
    ("go", 8),
    ("training_expired", 3),
    ("training_missing", 2),
    ("role_not_authorised", 3),
    ("ack_missing_or_old", 2),
    ("training_in_progress", 1),
    ("expired_and_ack_missing", 1),
]
FIRST = ["Asha", "Ravi", "Meera", "Kabir", "Nisha", "Arjun", "Leela", "Dev", "Tara", "Vikram"]


def _training(code: str, completed: date) -> dict[str, Any]:
    name, months = TRAININGS[code]
    return {
        "code": code,
        "name": name,
        "completed_on": completed,
        "expires_on": add_months(completed, months),
        "status": "completed",
    }


def build() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    r = rng("hr")
    profiles: list[dict[str, Any]] = []
    plants: list[dict[str, str]] = []
    n = 0
    for plant, count in PLAN:
        for k in range(count):
            n += 1
            emp_id = f"E{n:03d}"
            role = UNAUTHORISED[k % 2] if plant == "role_not_authorised" else AUTHORISED[n % 2]
            # Completed 1-8 months before AS_OF so every 12-month course is current.
            records = [
                _training(code, AS_OF_DATE - timedelta(days=r.randint(30, 240)))
                for code in TRAININGS
            ]
            ack: str | None = POLICY_VERSION
            if plant in ("training_expired", "expired_and_ack_missing"):
                code = ("FIN-101", "AML-201", "DPDP-101")[k % 3]
                months = TRAININGS[code][1]
                completed = add_months(AS_OF_DATE, -months) - timedelta(days=r.randint(5, 60))
                records = [x for x in records if x["code"] != code] + [_training(code, completed)]
            if plant == "training_missing":
                records = [x for x in records if x["code"] != ("AML-201", "DPDP-101")[k % 2]]
            if plant == "training_in_progress":
                records[0] = {
                    **records[0],
                    "status": "in_progress",
                    "completed_on": None,
                    "expires_on": None,
                }
            if plant == "ack_missing_or_old":
                ack = None if k == 0 else "v2"
            if plant == "expired_and_ack_missing":
                ack = None
            records.sort(key=lambda x: x["code"])
            profiles.append(
                {
                    "emp_id": emp_id,
                    "display_name": f"{FIRST[(n - 1) % len(FIRST)]} Synthetic-{n:02d}",
                    "role": role,
                    "department": "Finance" if role != "accounts_executive" else "Accounts",
                    "status": "active",
                    "trainings": records,
                    "policy_ack_version": ack,
                }
            )
            plants.append({"id": emp_id, "dataset": "S01 HR", "plant": plant})
    return profiles, plants


def _schema_view(p: dict[str, Any]) -> HrProfile:
    """The core HrProfile view; status is derived from expiry against AS_OF_DATE."""

    def status(t: dict[str, Any]) -> str:
        if t["status"] == "in_progress":
            return "in_progress"
        return "current" if t["expires_on"] >= AS_OF_DATE else "expired"

    return HrProfile(
        emp_id=p["emp_id"],
        display_name=p["display_name"],
        role=p["role"],
        trainings=[
            TrainingRecord(
                code=t["code"],
                name=t["name"],
                status=status(t),
                expires_on=t["expires_on"],
            )
            for t in p["trainings"]
        ],
        policy_ack_version=p["policy_ack_version"],
    )


def build_db(profiles: list[dict[str, Any]]) -> None:
    path = OUT / "hr.db"
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript(
            """
            CREATE TABLE employees(emp_id TEXT PRIMARY KEY, display_name TEXT, role TEXT,
                                   department TEXT, status TEXT);
            CREATE TABLE required_trainings(role TEXT, course_id TEXT, validity_months INTEGER,
                                            PRIMARY KEY(role, course_id));
            CREATE TABLE training_records(emp_id TEXT, course_id TEXT, status TEXT,
                                          completed_on TEXT, expires_on TEXT,
                                          PRIMARY KEY(emp_id, course_id));
            CREATE TABLE policy_acknowledgements(emp_id TEXT, policy_id TEXT, policy_version TEXT,
                                                 acknowledged_on TEXT);
            """
        )
        con.executemany(
            "INSERT INTO required_trainings VALUES (?, ?, ?)",
            [
                (role, code, months)
                for role in AUTHORISED
                for code, (_, months) in TRAININGS.items()
            ],
        )
        for p in profiles:
            con.execute(
                "INSERT INTO employees VALUES (?, ?, ?, ?, ?)",
                (p["emp_id"], p["display_name"], p["role"], p["department"], p["status"]),
            )
            for t in p["trainings"]:
                con.execute(
                    "INSERT INTO training_records VALUES (?, ?, ?, ?, ?)",
                    (
                        p["emp_id"],
                        t["code"],
                        t["status"],
                        t["completed_on"] and str(t["completed_on"]),
                        t["expires_on"] and str(t["expires_on"]),
                    ),
                )
            if p["policy_ack_version"]:
                con.execute(
                    "INSERT INTO policy_acknowledgements VALUES (?, ?, ?, ?)",
                    (
                        p["emp_id"],
                        POLICY_ID,
                        p["policy_ack_version"],
                        str(AS_OF_DATE - timedelta(days=90)),
                    ),
                )
        con.commit()
    finally:
        con.close()


def eval_users(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """S19: one preparer login per HR profile plus the five demo users. No passwords here."""
    users = [
        {"username": f"prep.{p['emp_id'].lower()}", "role": "preparer", "emp_id": p["emp_id"]}
        for p in profiles
    ]
    go = [p["emp_id"] for p in profiles if p["emp_id"] <= "E008"]
    users += [
        {"username": "demo.preparer", "role": "preparer", "emp_id": go[0]},
        {"username": "demo.preparer2", "role": "preparer", "emp_id": go[1]},
        {"username": "demo.director", "role": "director_finance", "emp_id": None},
        {"username": "demo.vp", "role": "vp_finance", "emp_id": None},
        {"username": "demo.evaluator", "role": "evaluator", "emp_id": None},
    ]
    return {
        "version": 1,
        "note": "Passwords are generated at seed time into the local DB only.",
        "users": users,
    }


def generate() -> list[dict[str, str]]:
    profiles, plants = build()
    for p in profiles:
        _schema_view(p)  # fail fast if the core schema rejects a profile
    write_json(OUT / "hr" / "profiles.json", profiles)
    build_db(profiles)
    write_yaml(OUT / "users" / "eval_users.yaml", eval_users(profiles))
    return plants
