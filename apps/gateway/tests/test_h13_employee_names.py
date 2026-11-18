"""H13 (ADR 0030 §2): the gateway loads hr.db employee names at startup and masks them in chat."""

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from credassure.security import pii

ROOT = Path(__file__).resolve().parents[3]
Login = Callable[[TestClient, str], dict[str, str]]


def _a_name() -> str:
    con = sqlite3.connect(f"file:{ROOT / 'data/frozen/v1/hr.db'}?mode=ro", uri=True)
    try:
        return str(con.execute("SELECT display_name FROM employees LIMIT 1").fetchone()[0])
    finally:
        con.close()


def test_H13_gateway_masks_hr_names_from_startup(client: TestClient) -> None:
    name = _a_name()
    assert pii.redact(f"ask {name} today") == "ask [REDACTED_EMPLOYEE_NAME] today"


def test_H13_name_in_chat_is_stored_redacted(
    make_client: Callable[..., Any], login: Login, new_case: Callable[[TestClient], str]
) -> None:
    client = make_client(llm_enabled=True)
    case_id = new_case(client)
    name = _a_name()
    h = login(client, "demo.preparer")
    r = client.post(f"/v1/cases/{case_id}/chat", json={"message": f"Is {name} trained?"}, headers=h)
    assert r.status_code == 200, r.text
    con = sqlite3.connect(client.db)
    try:
        stored = [r[0] for r in con.execute("SELECT redacted_text FROM chat_messages")]
    finally:
        con.close()
    assert stored and all(name.lower() not in t.lower() for t in stored)
    assert any("[REDACTED_EMPLOYEE_NAME]" in t for t in stored)


def test_H13_missing_hr_db_turns_name_masking_off(make_client: Callable[..., Any]) -> None:
    name = _a_name()
    make_client(hr_db=Path("/nonexistent/hr.db"))
    assert pii.redact(name) == name
    make_client()  # restore the names for later tests in this process


def test_H13_demo_refuses_to_start_without_hr_db() -> None:
    import pytest

    from credassure.gateway.main import _load_employee_names
    from credassure.gateway.settings import Settings

    demo = Settings(  # type: ignore[call-arg]
        _env_file=None,
        app_env="demo",
        jwt_secret="x" * 40,
        llm_enabled=False,
        hr_db=Path("/nonexistent/hr.db"),
    )
    with pytest.raises(RuntimeError, match="make hr-db"):
        _load_employee_names(demo)
    _load_employee_names(Settings(_env_file=None, app_env="test"))  # type: ignore[call-arg]
