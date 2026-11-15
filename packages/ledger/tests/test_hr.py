"""ONB-01/05: the HR reader reproduces the frozen profiles and has no write path."""

import json
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from credassure.ledger import hr, session

FROZEN = Path(__file__).resolve().parents[3] / "data" / "frozen" / "v1"


def test_ONB01_load_profile_matches_frozen_profiles_for_all_20() -> None:
    engine = session.hr_engine(FROZEN / "hr.db")
    profiles = json.loads((FROZEN / "hr" / "profiles.json").read_text())
    assert len(profiles) == 20
    for want in profiles:
        got = hr.load_profile(engine, want["emp_id"])
        assert got is not None
        assert got["role"] == want["role"]
        assert got["policy_ack_version"] == want.get("policy_ack_version")
        strip = [{k: t[k] for k in ("code", "status", "expires_on")} for t in want["trainings"]]
        mine = [{k: t[k] for k in ("code", "status", "expires_on")} for t in got["trainings"]]
        assert sorted(mine, key=str) == sorted(strip, key=str), want["emp_id"]


def test_ONB01_unknown_employee_is_none() -> None:
    assert hr.load_profile(session.hr_engine(FROZEN / "hr.db"), "E999") is None


def test_ONB05_hr_reader_engine_refuses_writes() -> None:
    engine = session.hr_engine(FROZEN / "hr.db")
    with pytest.raises(DBAPIError), engine.begin() as con:
        con.execute(text("UPDATE training_records SET status = 'completed'"))
