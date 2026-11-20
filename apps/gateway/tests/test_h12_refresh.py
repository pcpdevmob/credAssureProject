"""H12: token refresh up to a session cap; deactivated users, expired and too-old tokens refused."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi.testclient import TestClient

from credassure.security.auth import Principal, Role, issue_token, verify_token

Login = Callable[[TestClient, str], dict[str, str]]
SECRET = "x" * 40  # conftest: jwt_secret="x" * 40


def _claims(token: str) -> dict[str, Any]:
    return jwt.decode(token, options={"verify_signature": False})


def test_H12_refresh_returns_a_new_token_that_keeps_the_sign_in_time(
    client: TestClient, login: Login
) -> None:
    h = login(client, "demo.preparer")
    first = h["Authorization"][7:]
    r = client.post("/v1/auth/refresh", headers=h)
    assert r.status_code == 200, r.text
    new = r.json()["access_token"]
    assert r.json()["expires_in"] == 30 * 60
    assert _claims(new)["auth_time"] == _claims(first)["auth_time"]
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {new}"}).status_code == 200


def test_H12_refresh_needs_a_valid_token(client: TestClient) -> None:
    assert client.post("/v1/auth/refresh").status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert client.post("/v1/auth/refresh", headers=bad).status_code == 401


def test_H12_refresh_refuses_an_expired_token(client: TestClient, login: Login) -> None:
    who = verify_token(login(client, "demo.preparer")["Authorization"][7:], SECRET)
    old = issue_token(who, SECRET, 30, now=datetime.now(UTC) - timedelta(minutes=31))
    r = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {old}"})
    assert r.status_code == 401


def test_H12_session_cap_cannot_be_extended_by_refreshing(client: TestClient, login: Login) -> None:
    who = verify_token(login(client, "demo.preparer")["Authorization"][7:], SECRET)
    signed_in = datetime.now(UTC) - timedelta(minutes=241)
    token = issue_token(who, SECRET, 30, auth_time=signed_in)  # valid now, session too old
    r = client.post("/v1/auth/refresh", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401 and "sign in again" in r.json()["detail"]


def test_H12_a_deactivated_user_cannot_refresh(client: Any, login: Login) -> None:
    from sqlalchemy import text

    from credassure.ledger.session import case_engine

    h = login(client, "demo.preparer")
    engine = case_engine(client.db)  # SQLite or MySQL (ADR 0039)
    with engine.begin() as conn:
        conn.execute(text("UPDATE users SET active = 0 WHERE username = 'demo.preparer'"))
    engine.dispose()
    assert client.post("/v1/auth/refresh", headers=h).status_code == 401


def test_H12_auth_time_defaults_to_the_issue_time() -> None:
    from credassure.security.auth import token_auth_time

    now = datetime.now(UTC).replace(microsecond=0)
    token = issue_token(Principal("u", Role.PREPARER, "t"), SECRET, 5, now=now)
    assert token_auth_time(token, SECRET) == now
