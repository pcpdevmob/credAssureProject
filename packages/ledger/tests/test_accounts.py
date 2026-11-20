"""ADR 0038: account columns migrate up and down, account writes are allow-listed and audited
without secrets, revocation bumps token_version, and the first admin is bootstrapped once."""

from pathlib import Path

import pytest
from sqlalchemy import inspect

from credassure.ledger import migrate, reads, seed, session, writes
from credassure.ledger.errors import ConflictError
from credassure.security.auth import hash_password

COLUMNS = {
    "display_name",
    "must_change_password",
    "mfa_enabled",
    "mfa_secret",
    "mfa_last_step",
    "mfa_backup",
    "token_version",
    "created_at",
    "updated_at",
}


def _db(tmp_path: Path) -> Path:
    db = tmp_path / "case.db"
    migrate.upgrade("case", db)
    return db


def test_ADR0038_migration_adds_account_columns_and_downgrade_removes_them(tmp_path: Path) -> None:
    db = _db(tmp_path)
    cols = {c["name"] for c in inspect(session.case_engine(db)).get_columns("users")}
    assert cols >= COLUMNS
    migrate.downgrade("case", db, "7d2b9e4c1a30")
    cols = {c["name"] for c in inspect(session.case_engine(db)).get_columns("users")}
    assert not COLUMNS & cols
    migrate.upgrade("case", db)


def test_ADR0038_account_changes_are_audited_without_secrets_and_revoke(tmp_path: Path) -> None:
    engine = session.case_engine(_db(tmp_path))
    with session.transaction(engine) as s:
        u = writes.create_user(
            s,
            tenant_id="default",
            actor="u-admin",
            username="anita.director",
            role="director_finance",
            password_hash=hash_password("brass-otter-rainfall-41"),
        )
        assert u.must_change_password and u.token_version == 0 and not u.mfa_enabled
        writes.update_user(
            s,
            user_id=u.id,
            tenant_id="default",
            actor="u-admin",
            event_type="MFA_ENROLLED",
            changes={"mfa_secret": "v1:SEALED", "mfa_enabled": True, "mfa_backup": ["h1"]},
            payload={"secret": "LEAK", "by": "u-admin"},
            revoke=True,
        )
        assert u.token_version == 1
        with pytest.raises(ValueError, match="not an account field"):
            writes.update_user(
                s, user_id=u.id, tenant_id="default", actor="x", changes={"tenant_id": "other"}
            )
        with pytest.raises(ConflictError):
            writes.update_user(s, user_id=u.id, tenant_id="other", actor="x", changes={})
        with pytest.raises(ConflictError):
            writes.create_user(
                s,
                tenant_id="default",
                actor="x",
                username="anita.director",
                role="preparer",
                password_hash="h",
            )
        events = reads.account_events(s, "default")
    assert [e.event_type for e in events] == ["MFA_ENROLLED", "USER_CREATED"]
    body = str([e.payload for e in events])
    assert "SEALED" not in body and "LEAK" not in body and "h1" not in body
    assert events[0].payload["fields"] == ["mfa_backup", "mfa_enabled", "mfa_secret"]
    assert events[0].payload["by"] == "u-admin"


def test_ADR0038_bootstrap_admin_once_with_a_policy_password(tmp_path: Path) -> None:
    db = tmp_path / "case.db"
    with pytest.raises(SystemExit, match="at least 12"):
        seed.bootstrap_admin(db, "root.admin", "short")
    seed.bootstrap_admin(db, "root.admin", "brass-otter-rainfall-41")
    engine = session.case_engine(db)
    with session.transaction(engine) as s:
        admin = reads.user_by_name(s, "root.admin")
        assert admin is not None and admin.role == "user_admin" and admin.must_change_password
        assert reads.active_admins(s, "default") == 1
    with pytest.raises(SystemExit, match="already has an active user_admin"):
        seed.bootstrap_admin(db, "second.admin", "brass-otter-rainfall-42")
