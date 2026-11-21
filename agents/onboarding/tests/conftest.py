"""Shared test setup: a fresh synthetic HR store and case database per test, model switched off."""
import pytest

from readiness import generate_hr_data as gen


@pytest.fixture()
def hr_env(tmp_path, monkeypatch):
    emps, recs, acks, _ = gen.build_profiles()
    gen.write_db(tmp_path / "hr.db", emps, recs, acks)
    (tmp_path / "user_map.json").write_text('{"preparer@finbridge.demo": "EMP-001", "blocked@finbridge.demo": "EMP-007"}')
    monkeypatch.setenv("CREDASSURE_HR_DB", str(tmp_path / "hr.db"))
    monkeypatch.setenv("CREDASSURE_DB", str(tmp_path / "credassure.db"))
    monkeypatch.setenv("CREDASSURE_USER_MAP", str(tmp_path / "user_map.json"))
    monkeypatch.setenv("CREDASSURE_LLM_BACKOFF", "0.01,0.01")
    for k in ("CREDASSURE_LLM_BASE_URL", "CREDASSURE_LLM_MODEL", "CREDASSURE_LLM_CA_CERT",
              "CREDASSURE_LLM_EXTRA_BODY", "CREDASSURE_LLM_NO_THINK"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path
