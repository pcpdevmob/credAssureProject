"""Scope #40: the copilot first-use notice and its acknowledgement are stored server-side, per user
and notice version, as an audit event (user decision 2(a): the first question also counts)."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

Login = Callable[[TestClient, str], dict[str, str]]
URL = "/v1/me/chat-notice"


def test_scope40_notice_starts_unacknowledged_and_ack_persists_per_user(
    client: TestClient, login: Login
) -> None:
    p, d = login(client, "demo.preparer"), login(client, "demo.director")
    first = client.get(URL, headers=p).json()
    assert first["acknowledged_at"] is None
    assert "not legal, tax or credit advice" in first["text"] and len(first["version"]) == 12

    r = client.post(f"{URL}/ack", headers=p)
    assert r.status_code == 200 and r.json()["acknowledged_at"]
    again = login(client, "demo.preparer")  # a new login still sees it acknowledged
    assert client.get(URL, headers=again).json()["acknowledged_at"] == r.json()["acknowledged_at"]
    assert client.get(URL, headers=d).json()["acknowledged_at"] is None  # another user's is not
    assert client.post(f"{URL}/ack", headers=p).json() == r.json()  # idempotent: one event


def test_scope40_first_question_records_the_acknowledgement(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    p = login(client, "demo.preparer")
    case_id = new_case(client)
    reply = client.post(f"/v1/cases/{case_id}/chat", json={"message": "What is a KFS?"}, headers=p)
    assert "not legal" in reply.json()["notice"]
    assert client.get(URL, headers=p).json()["acknowledged_at"]
    other = new_case(client)  # acknowledged once: no notice in another case either
    reply = client.post(f"/v1/cases/{other}/chat", json={"message": "What is a KFS?"}, headers=p)
    assert "notice" not in reply.json()


def test_scope40_changed_notice_asks_again(
    client: TestClient, login: Login, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = login(client, "demo.preparer")
    client.post(f"{URL}/ack", headers=p)
    from credassure.gateway import supervisor_service

    monkeypatch.setattr(supervisor_service, "CHAT_NOTICE", supervisor_service.CHAT_NOTICE + " New.")
    assert client.get(URL, headers=p).json()["acknowledged_at"] is None


def test_scope40_ack_is_audited_and_needs_auth(client: TestClient, login: Login) -> None:
    assert client.post(f"{URL}/ack").status_code == 401
    client.post(f"{URL}/ack", headers=login(client, "demo.preparer"))
    from sqlalchemy import text

    from credassure.ledger.session import transaction

    svc: Any = client.app.state.services  # type: ignore[attr-defined]
    with transaction(svc.engine) as s:
        n = s.execute(
            text("SELECT count(*) FROM audit_log WHERE event_type = 'CHAT_NOTICE_ACKNOWLEDGED'")
        ).scalar_one()
    assert n == 1
