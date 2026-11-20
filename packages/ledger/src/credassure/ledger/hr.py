"""Read one preparer's HR profile from hr.db (ONB-01, ONB-05). SELECT only; open with hr_engine.

Returns the shape `engines.onboarding_rules.evaluate` reads: role, trainings[{code, status,
completed_on, expires_on}], policy_ack_version (the newest WC-POL version acknowledged).
"""

from typing import Any

from sqlalchemy import Engine, text

POLICY_ID = "WC-POL"


def load_profile(engine: Engine, emp_id: str) -> dict[str, Any] | None:
    with engine.connect() as con:
        emp = con.execute(
            text("SELECT emp_id, role, status FROM employees WHERE emp_id = :e"), {"e": emp_id}
        ).first()
        if emp is None or emp.status != "active":
            return None  # fail closed: no active HR record -> NEEDS_INPUT, never GO
        trainings = [
            {"code": r[0], "status": r[1], "completed_on": r[2], "expires_on": r[3]}
            for r in con.execute(
                text(
                    "SELECT course_id, status, completed_on, expires_on FROM training_records"
                    " WHERE emp_id = :e ORDER BY course_id"
                ),
                {"e": emp_id},
            )
        ]
        ack = con.execute(
            text(
                "SELECT policy_version FROM policy_acknowledgements"
                " WHERE emp_id = :e AND policy_id = :p"
                " ORDER BY acknowledged_on DESC, policy_version DESC LIMIT 1"
            ),
            {"e": emp_id, "p": POLICY_ID},
        ).scalar()
    return {
        "emp_id": emp.emp_id,
        "role": emp.role,
        "status": emp.status,
        "trainings": trainings,
        "policy_ack_version": ack,
    }


def display_names(engine: Engine) -> list[str]:
    """Every employee's display name, for exact-match masking in free text (H13, ADR 0030 §2)."""
    with engine.connect() as con:
        return [str(r[0]) for r in con.execute(text("SELECT display_name FROM employees")) if r[0]]
