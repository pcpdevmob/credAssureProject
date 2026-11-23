"""ADR 0038 accounts: `make db` / `make passwords` give every account its own password.

No shared SEED_PASSWORD; SEED_PASSWORD_<USER> sets one account (kept); every other account gets a
random first password it must change at first sign-in. Values are never echoed in errors.
"""

from pathlib import Path

import pytest
from sqlalchemy import select

from credassure.ledger import models, reads, seed, session, writes
from credassure.security import password_policy
from credassure.security.auth import verify_password

ACCOUNTS = 25  # S08 demo users + S19 eval preparers (data/frozen/v1/users/eval_users.yaml)


def _users(db: Path) -> dict[str, models.User]:
    with session.transaction(session.case_engine(db)) as s:
        users = {u.username: u for u in s.scalars(select(models.User))}
        for u in users.values():
            s.expunge(u)
    return users


def test_ADR0038_every_account_gets_its_own_first_password(tmp_path: Path) -> None:
    db = tmp_path / "case.db"
    issued = seed.issue_passwords(db, {"SEED_PASSWORD": "shared-pass-0001"})
    assert len(issued) == ACCOUNTS
    assert len({i.password for i in issued}) == ACCOUNTS  # no two accounts share one
    assert all(i.temporary for i in issued)
    users = _users(db)
    for i in issued:
        u = users[i.username]
        assert password_policy.problems(i.password, i.username) == []
        assert verify_password(u.password_hash, i.password)
        assert u.must_change_password is True  # changed at first sign-in
        assert not verify_password(u.password_hash, "shared-pass-0001")  # shared one ignored
    assert users["demo.director"].role == "director_finance"
    assert users["demo.preparer"].emp_id == "E001"
    assert seed.issue_passwords(db, {}) == []  # idempotent: existing accounts kept
    raw = db.read_bytes().decode("latin-1")
    assert not any(i.password in raw for i in issued)  # only argon2 hashes are stored


def test_ADR0038_env_password_sets_one_account_and_is_kept(tmp_path: Path) -> None:
    db = tmp_path / "case.db"
    env = {"SEED_PASSWORD_DEMO_PREPARER": "prep-own-pass-01"}
    issued = {i.username: i for i in seed.issue_passwords(db, env)}
    assert issued["demo.preparer"].temporary is False
    assert issued["demo.preparer"].password == "prep-own-pass-01"
    users = _users(db)
    assert users["demo.preparer"].must_change_password is False  # scripts sign in with it
    assert verify_password(users["demo.preparer"].password_hash, "prep-own-pass-01")
    assert users["demo.vp"].must_change_password is True


def test_ADR0038_two_accounts_with_one_password_are_refused(tmp_path: Path) -> None:
    env = {
        "SEED_PASSWORD_DEMO_VP": "same-pass-00001",
        "SEED_PASSWORD_DEMO_DIRECTOR": "same-pass-00001",
    }
    with pytest.raises(SystemExit) as exc:
        seed.issue_passwords(tmp_path / "case.db", env)
    message = str(exc.value)
    assert "SEED_PASSWORD_DEMO_VP" in message and "SEED_PASSWORD_DEMO_DIRECTOR" in message
    assert "same-pass-00001" not in message
    with pytest.raises(SystemExit) as weak:
        seed.issue_passwords(tmp_path / "case.db", {"SEED_PASSWORD_DEMO_VP": "short"})
    assert "SEED_PASSWORD_DEMO_VP" in str(weak.value) and "short" not in str(weak.value)
    assert not (tmp_path / "case.db").exists()  # refused before anything is written


def test_ADR0038_reissue_resets_every_seeded_account_signs_out_keeps_mfa(tmp_path: Path) -> None:
    db = tmp_path / "case.db"
    first = {i.username: i.password for i in seed.issue_passwords(db, {})}
    with session.transaction(session.case_engine(db)) as s:
        writes.update_user(
            s,
            user_id="u-demo.vp",
            tenant_id="default",
            actor="test",
            changes={"mfa_enabled": True, "must_change_password": False},
        )
        writes.add_user(  # an account in another tenant is not touched
            s, user_id="u-other", tenant_id="other", username="other.admin", role="user_admin",
            password_hash="x",
        )  # fmt: skip
    before = _users(db)
    again = {i.username: i for i in seed.issue_passwords(db, {}, reissue=True)}
    assert set(again) == set(first)
    assert all(again[u].password != first[u] for u in first)
    after = _users(db)
    assert after["demo.vp"].mfa_enabled is True  # MFA enrolment kept
    assert after["demo.vp"].must_change_password is True
    assert after["demo.vp"].token_version == (before["demo.vp"].token_version or 0) + 1
    assert verify_password(after["demo.vp"].password_hash, again["demo.vp"].password)
    assert after["other.admin"].password_hash == "x"
    with session.transaction(session.case_engine(db)) as s:
        assert reads.verify_chain(s) == []
        resets = s.execute(
            select(models.AuditLog).where(models.AuditLog.event_type == "PASSWORD_RESET")
        ).all()
    assert len(resets) == ACCOUNTS


def test_ADR0038_generated_passwords_are_readable_and_strong() -> None:
    made = {seed.new_password() for _ in range(500)}
    assert len(made) == 500
    for pw in made:
        assert len(pw) == 19 and pw.count("-") == 3
        assert not set(pw) & set("01lIoO")  # nothing that reads as another character
        assert password_policy.problems(pw) == []


def test_ADR0038_seed_cli_needs_an_explicit_test_password(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(SystemExit):
        seed.main([str(tmp_path / "e2e.db")])  # the app database goes through make db
    monkeypatch.setenv("E2E_PASSWORD", "e2e-fixture-001")
    assert seed.main([str(tmp_path / "e2e.db"), "--password-env", "E2E_PASSWORD"]) == 0
    users = _users(tmp_path / "e2e.db")
    assert verify_password(users["demo.preparer"].password_hash, "e2e-fixture-001")
