"""ADR 0038 through the API: staged sign-in, TOTP enrolment and verification, password change,
revocation, the admin users API, segregation of duties and the MFA step-up above ₹1.5 crore."""

import base64
import os
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from credassure.security import mfa

PASSWORD = "fixture-password-123"  # conftest.PASSWORD
ADMIN_PASSWORD = "brass-otter-rainfall-41"
KEY = base64.b64encode(os.urandom(32)).decode()
Login = Callable[[TestClient, str], dict[str, str]]


class Clock:
    """A TOTP clock the test moves: every code is for a later step, so none is a replay."""

    def __init__(self) -> None:
        self.t = 1_900_000_000.0

    def tick(self) -> float:
        self.t += mfa.STEP
        return self.t

    def code(self, secret: str) -> str:
        return mfa.totp_at(secret, mfa.step_of(self.tick()))


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    from credassure.gateway import accounts
    from credassure.gateway.routers import auth

    c = Clock()
    fake = SimpleNamespace(time=lambda: c.t)
    monkeypatch.setattr(accounts, "time", fake)
    monkeypatch.setattr(auth, "time", fake)
    return c


@pytest.fixture
def app(make_client: Callable[..., Any]) -> Any:
    """MFA enforced for approvers and admins, as in production."""
    return make_client(mfa_enforced=True, mfa_encryption_key=KEY)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _sign_in(client: TestClient, username: str, password: str = PASSWORD) -> dict[str, Any]:
    r = client.post("/v1/auth/token", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return dict(r.json())


def _enrol(
    client: TestClient, token: str, clock: Clock, password: str = PASSWORD
) -> tuple[str, dict[str, Any]]:
    setup = client.post(
        "/v1/auth/mfa/setup", json={"current_password": password}, headers=_bearer(token)
    )
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    done = client.post(
        "/v1/auth/mfa/enable", json={"code": clock.code(secret)}, headers=_bearer(token)
    )
    assert done.status_code == 200, done.text
    return secret, dict(done.json())


def _admin(client: Any, clock: Clock, username: str = "root.admin") -> dict[str, str]:
    """The bootstrap admin of this test DB, signed in fully (password changed, MFA enrolled)."""
    from credassure.ledger import session, writes
    from credassure.security.auth import hash_password

    with session.transaction(session.case_engine(client.db)) as s:
        writes.create_user(
            s,
            tenant_id="default",
            actor="bootstrap",
            username=username,
            role="user_admin",
            password_hash=hash_password(ADMIN_PASSWORD),
            must_change_password=False,
        )
    first = _sign_in(client, username, ADMIN_PASSWORD)
    assert first["stage"] == "setup" and first["next"] == ["enrol_mfa"]
    _, full = _enrol(client, first["access_token"], clock, ADMIN_PASSWORD)
    assert full["stage"] == "full"
    return _bearer(full["access_token"])


def test_ADR0038_approver_must_enrol_and_a_setup_token_opens_nothing_else(
    app: Any, clock: Clock
) -> None:
    first = _sign_in(app, "demo.director")
    assert first["stage"] == "setup" and first["next"] == ["enrol_mfa"]
    setup = _bearer(first["access_token"])
    assert app.get("/v1/cases", headers=setup).status_code == 401
    assert app.post("/v1/auth/refresh", headers=setup).status_code == 401
    me = app.get("/v1/me", headers=setup).json()
    assert me["mfa_required"] and not me["mfa_enabled"] and me["stage"] == "setup"
    _, done = _enrol(app, first["access_token"], clock)
    assert len(done["backup_codes"]) == 8 and done["stage"] == "full"
    assert app.get("/v1/cases", headers=_bearer(done["access_token"])).status_code == 200
    assert app.get("/v1/me", headers=setup).status_code == 401  # enrolment revoked it


def test_ADR0038_a_preparer_signs_in_with_a_password_only(app: Any) -> None:
    assert _sign_in(app, "demo.preparer")["stage"] == "full"  # MFA required for approvers only


def test_ADR0038_second_factor_at_sign_in_replay_backup_codes_and_limit(
    app: Any, clock: Clock
) -> None:
    first = _sign_in(app, "demo.vp")
    secret, done = _enrol(app, first["access_token"], clock)
    backup = done["backup_codes"]

    pending = _sign_in(app, "demo.vp")
    assert pending["stage"] == "mfa" and pending["next"] == ["verify_mfa"]
    h = _bearer(pending["access_token"])
    assert app.get("/v1/me", headers=h).status_code == 401  # an mfa token opens only verify
    assert app.get("/v1/cases", headers=h).status_code == 401
    code = clock.code(secret)
    ok = app.post("/v1/auth/mfa/verify", json={"code": code}, headers=h)
    assert ok.status_code == 200 and ok.json()["stage"] == "full", ok.text

    again = _bearer(_sign_in(app, "demo.vp")["access_token"])
    replay = app.post("/v1/auth/mfa/verify", json={"code": code}, headers=again)
    assert replay.status_code == 401  # the same code twice
    used = app.post("/v1/auth/mfa/verify", json={"code": backup[0]}, headers=again)
    assert used.status_code == 200, used.text
    third = _bearer(_sign_in(app, "demo.vp")["access_token"])
    assert (
        app.post("/v1/auth/mfa/verify", json={"code": backup[0]}, headers=third).status_code == 401
    )

    statuses = [
        app.post("/v1/auth/mfa/verify", json={"code": "000000"}, headers=third).status_code
        for _ in range(6)
    ]
    assert statuses[-1] == 429
    good = app.post("/v1/auth/mfa/verify", json={"code": clock.code(secret)}, headers=third)
    assert good.status_code == 429  # a right code is refused too while limited


def test_ADR0038_admin_creates_a_user_who_must_change_the_temporary_password(
    app: Any, clock: Clock
) -> None:
    admin = _admin(app, clock)
    r = app.post(
        "/v1/admin/users",
        json={
            "username": "ravi.prep",
            "display_name": "Ravi",
            "role": "preparer",
            "emp_id": "E999",
        },
        headers=admin,
    )
    assert r.status_code == 201, r.text
    temporary = r.json()["temporary_password"]
    assert r.json()["user"]["must_change_password"] and "password_hash" not in r.json()["user"]

    first = _sign_in(app, "ravi.prep", temporary)
    assert first["stage"] == "setup" and first["next"] == ["change_password"]
    h = _bearer(first["access_token"])
    weak = app.post(
        "/v1/auth/password",
        json={"current_password": temporary, "new_password": "Password@2026"},
        headers=h,
    )
    assert weak.status_code == 422 and "too common" in weak.json()["detail"]
    done = app.post(
        "/v1/auth/password",
        json={"current_password": temporary, "new_password": "lantern-quiet-harbour-7"},
        headers=h,
    )
    assert done.status_code == 200 and done.json()["stage"] == "full", done.text
    assert app.get("/v1/me", headers=h).status_code == 401  # revoked by the change
    bad = app.post("/v1/auth/token", json={"username": "ravi.prep", "password": temporary})
    assert bad.status_code == 401
    assert _sign_in(app, "ravi.prep", "lantern-quiet-harbour-7")["stage"] == "full"

    dup = app.post(
        "/v1/admin/users",
        json={"username": "ravi.prep", "display_name": "R", "role": "preparer"},
        headers=admin,
    )
    assert dup.status_code == 409
    approver_bound = app.post(
        "/v1/admin/users",
        json={"username": "x.dir", "display_name": "X", "role": "vp_finance", "emp_id": "E004"},
        headers=admin,
    )
    assert approver_bound.status_code == 422


def test_ADR0038_segregation_of_duties(app: Any, clock: Clock, login: Login) -> None:
    admin = _admin(app, clock)
    assert app.get("/v1/cases", headers=admin).status_code == 403
    assert app.post("/v1/copilot/chat", json={"message": "hi"}, headers=admin).status_code == 403
    for user in ("demo.preparer", "demo.evaluator"):
        assert app.get("/v1/admin/users", headers=login(app, user)).status_code == 403
    assert app.get("/v1/admin/users", headers=admin).status_code == 200
    me = app.get("/v1/me", headers=admin).json()
    own = me["user_id"]
    assert app.post(f"/v1/admin/users/{own}/disable", headers=admin).status_code == 403
    r = app.post(f"/v1/admin/users/{own}/role", json={"role": "vp_finance"}, headers=admin)
    assert r.status_code == 403
    assert app.post(f"/v1/admin/users/{own}/reset-mfa", headers=admin).status_code == 403


def test_ADR0038_role_change_disable_resets_and_logout_revoke_tokens(
    app: Any, clock: Clock, login: Login
) -> None:
    admin = _admin(app, clock)
    prep = login(app, "demo.preparer")
    target = "u-demo.preparer"
    r = app.post(f"/v1/admin/users/{target}/role", json={"role": "evaluator"}, headers=admin)
    assert r.status_code == 200 and r.json()["role"] == "evaluator"
    assert app.get("/v1/cases", headers=prep).status_code == 401
    ev = login(app, "demo.preparer")
    assert app.post(f"/v1/admin/users/{target}/disable", headers=admin).status_code == 200
    assert app.get("/v1/cases", headers=ev).status_code == 401
    assert (
        app.post(
            "/v1/auth/token", json={"username": "demo.preparer", "password": PASSWORD}
        ).status_code
        == 401
    )
    assert app.post(f"/v1/admin/users/{target}/enable", headers=admin).status_code == 200

    reset = app.post(f"/v1/admin/users/{target}/reset-password", headers=admin)
    assert reset.status_code == 200
    assert (
        app.post(
            "/v1/auth/token", json={"username": "demo.preparer", "password": PASSWORD}
        ).status_code
        == 401
    )
    assert _sign_in(app, "demo.preparer", reset.json()["temporary_password"])["stage"] == "setup"

    first = _sign_in(app, "demo.director")
    _, done = _enrol(app, first["access_token"], clock)
    assert app.post("/v1/admin/users/u-demo.director/reset-mfa", headers=admin).status_code == 200
    again = _sign_in(app, "demo.director")
    assert again["stage"] == "setup" and again["next"] == ["enrol_mfa"]  # must enrol anew
    assert app.get("/v1/me", headers=_bearer(done["access_token"])).status_code == 401

    ev2 = login(app, "demo.evaluator")
    ev3 = login(app, "demo.evaluator")
    assert app.post("/v1/auth/logout", headers=ev2).json() == {"signed_out": True}
    assert app.get("/v1/cases", headers=ev3).status_code == 401  # everywhere

    events = app.get("/v1/admin/users/events", headers=admin)
    assert events.status_code == 200
    kinds = [e["event_type"] for e in events.json()]
    for kind in (
        "USER_ROLE_CHANGED",
        "USER_DISABLED",
        "USER_ENABLED",
        "PASSWORD_RESET",
        "MFA_ENROLLED",
        "MFA_RESET",
        "SIGNED_OUT",
        "LOGIN_FAILED",
        "USER_CREATED",
    ):
        assert kind in kinds, kind
    text = events.text
    assert reset.json()["temporary_password"] not in text and "v1:" not in text


def test_ADR0038_the_last_active_admin_cannot_be_demoted_or_disabled(app: Any) -> None:
    from credassure.gateway.problems import ProblemError
    from credassure.gateway.routers.users import _keeps_an_admin
    from credassure.ledger import reads, session, writes
    from credassure.security.auth import hash_password

    with session.transaction(session.case_engine(app.db)) as s:
        only = writes.create_user(
            s,
            tenant_id="default",
            actor="t",
            username="solo.admin",
            role="user_admin",
            password_hash=hash_password(ADMIN_PASSWORD),
        )
        assert reads.active_admins(s, "default") == 1
        with pytest.raises(ProblemError) as refused:
            _keeps_an_admin(s, only, "default")
        assert refused.value.status == 409


def test_ADR0038_step_up_above_threshold_needs_a_code_once_enrolled(
    app: Any, clock: Clock, new_case: Callable[[TestClient], str]
) -> None:
    from credassure.gateway import report
    from credassure.ledger import reads
    from credassure.ledger.session import transaction

    first = _sign_in(app, "demo.vp")
    secret, done = _enrol(app, first["access_token"], clock)
    vp = _bearer(done["access_token"])
    case_id = new_case(app)
    svc = app.app.state.services
    for key, value, unit in (
        ("wc.gate", "GO", "enum"),
        ("wc.recommended_amount", 15_000_001, "INR"),
    ):
        svc.ledger.put_fact(
            case_id, key, value, unit=unit, source_type="test", source_ref="t", produced_by="t"
        )
    svc.ledger.route(case_id, "vp_finance")
    with transaction(svc.engine) as s:
        case = reads.get_case(s, svc.settings.tenant_id, case_id)
    assert case is not None
    report.snapshot(svc.engine, case, svc.ledger.put_fact)

    def approve(**extra: Any) -> Any:
        version = app.get(f"/v1/cases/{case_id}", headers=vp).json()["row_version"]
        body = {
            "decision": "approve",
            "attested": True,
            "comment": "ok",
            "expected_version": version,
            **extra,
        }
        return app.post(f"/v1/cases/{case_id}/decision", json=body, headers=vp)

    r = approve(password=PASSWORD)
    assert r.status_code == 403 and "code from your app" in r.json()["detail"]
    assert approve(password=PASSWORD, mfa_code="123456").status_code == 403
    ok = approve(password=PASSWORD, mfa_code=clock.code(secret))
    assert ok.status_code == 200 and ok.json()["status"] == "APPROVED", ok.text


def test_ADR0038_mfa_off_in_the_test_profile_keeps_the_old_sign_in(client: Any) -> None:
    r = client.post("/v1/auth/token", json={"username": "demo.vp", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["stage"] == "full" and r.json()["next"] == []


def test_ADR0038_enrolment_without_a_key_is_refused(make_client: Callable[..., Any]) -> None:
    c = make_client(mfa_enforced=False)
    token = _sign_in(c, "demo.vp")["access_token"]
    body = {"current_password": PASSWORD}
    assert c.post("/v1/auth/mfa/setup", json=body, headers=_bearer(token)).status_code == 503


def test_ADR0038_settings_refuse_a_bad_key_and_require_one_when_enforced() -> None:
    from pydantic import ValidationError

    from credassure.gateway.settings import Settings

    with pytest.raises(ValidationError, match="32 bytes"):
        Settings(_env_file=None, app_env="test", mfa_encryption_key="c2hvcnQ=")
    with pytest.raises(ValidationError, match="MFA_ENCRYPTION_KEY is required"):
        Settings(_env_file=None, app_env="dev", jwt_secret="x" * 40, llm_enabled=False)
    ok = Settings(
        _env_file=None, app_env="dev", jwt_secret="x" * 40, llm_enabled=False, mfa_enforced=False
    )
    assert not ok.mfa_required_for("vp_finance")


def test_ADR0038_review_a_stolen_token_alone_cannot_bind_an_attackers_app(app: Any) -> None:
    """MUST from the security review: enrolment needs the password again."""
    stolen = _bearer(_sign_in(app, "demo.preparer")["access_token"])  # full, MFA optional
    assert app.post("/v1/auth/mfa/setup", headers=stolen).status_code == 422
    wrong = app.post(
        "/v1/auth/mfa/setup", json={"current_password": "not-the-password"}, headers=stolen
    )
    assert wrong.status_code == 403
    assert app.get("/v1/cases", headers=stolen).status_code == 200  # nothing was revoked


def test_ADR0038_review_enrolment_keeps_the_session_clock(app: Any, clock: Clock) -> None:
    import jwt

    first = _sign_in(app, "demo.director")
    _, done = _enrol(app, first["access_token"], clock)

    def claims(tok: str) -> dict[str, Any]:
        return dict(jwt.decode(tok, options={"verify_signature": False}))

    assert claims(done["access_token"])["auth_time"] == claims(first["access_token"])["auth_time"]


def test_ADR0038_review_password_alone_cannot_sign_the_user_out(app: Any, clock: Clock) -> None:
    first = _sign_in(app, "demo.vp")
    _, done = _enrol(app, first["access_token"], clock)
    pending = _bearer(_sign_in(app, "demo.vp")["access_token"])  # stage mfa
    assert app.post("/v1/auth/logout", headers=pending).status_code == 401
    assert app.get("/v1/me", headers=_bearer(done["access_token"])).status_code == 200


def test_ADR0038_review_one_code_cannot_be_spent_twice_from_a_stale_row(
    app: Any, clock: Clock
) -> None:
    from credassure.gateway import accounts
    from credassure.ledger import reads
    from credassure.ledger.session import transaction

    first = _sign_in(app, "demo.vp")
    secret, done = _enrol(app, first["access_token"], clock)
    svc = app.app.state.services
    with transaction(svc.engine) as s:
        stale = reads.get_user(s, "u-demo.vp")
    assert stale is not None
    code = clock.code(secret)
    assert accounts.check_second_factor(svc, stale, code, actor="t")
    assert not accounts.check_second_factor(svc, stale, code, actor="t")  # re-read, refused
    backup = done["backup_codes"][0]
    assert accounts.check_second_factor(svc, stale, backup, actor="t")
    assert not accounts.check_second_factor(svc, stale, backup, actor="t")


def test_ADR0038_review_one_login_per_hr_profile(app: Any, clock: Clock) -> None:
    admin = _admin(app, clock)
    r = app.post(
        "/v1/admin/users",
        json={"username": "copy.prep", "display_name": "C", "role": "preparer", "emp_id": "E001"},
        headers=admin,
    )
    assert r.status_code == 409 and "HR id" in r.json()["detail"]  # demo.preparer holds E001


def test_ADR0038_review_an_empty_key_is_unset() -> None:
    from credassure.gateway.settings import Settings

    s = Settings(_env_file=None, app_env="test", mfa_encryption_key="")
    assert s.mfa_encryption_key is None
