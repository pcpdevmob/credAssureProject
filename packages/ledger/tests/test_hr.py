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


def test_scope22_hr_reads_from_many_threads_do_not_share_connections() -> None:
    """The load smoke (scope #35) reads HR profiles from more than five threads at once. A pooled
    "sqlite://" engine (SingletonThreadPool) closed other threads' connections mid-query
    (segfault on CI); each read now opens its own read-only connection."""
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy.pool import NullPool

    engine = session.hr_engine(FROZEN / "hr.db")
    assert isinstance(engine.pool, NullPool)
    ids = [f"E{n:03d}" for n in range(1, 21)] * 10
    with ThreadPoolExecutor(max_workers=16) as pool:
        got = list(pool.map(lambda e: hr.load_profile(engine, e), ids))
    assert sum(p is not None for p in got) == sum(
        hr.load_profile(engine, e) is not None for e in ids
    )
