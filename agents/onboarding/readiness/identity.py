"""Works out which synthetic employee is the preparer for a readiness check.

Order: an explicit employee ID (preparerId) -> the logged-in UI user, via the user map ->
the preparer recorded on the case. The user map (data/user_map.json, or the file named by
CREDASSURE_USER_MAP) links UI logins such as preparer@finbridge.demo to HR employee IDs,
because the UI's demo accounts are not HR records.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_MAP = Path(__file__).resolve().parent.parent / "data" / "user_map.json"


def user_map() -> dict:
    path = Path(os.getenv("CREDASSURE_USER_MAP", DEFAULT_MAP))
    try:
        return {k.lower(): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}
    except (OSError, ValueError):
        return {}


def resolve_preparer(preparer_id: Optional[str], user: Optional[str], case: Optional[dict]) -> tuple[Optional[str], str]:
    """Returns (employee_id or None, how it was found)."""
    if preparer_id:
        return preparer_id, "preparer_id"
    if user:
        emp = user_map().get(user.strip().lower())
        if emp:
            return emp, "user_map"
    if case and case.get("preparer_id"):
        return case["preparer_id"], "case"
    return None, "none"
