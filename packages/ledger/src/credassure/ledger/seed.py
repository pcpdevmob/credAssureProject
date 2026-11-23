"""Seed users into case.db (S08 demo users + S19 eval preparers). Kept apart from migrations (#29).

The app's own accounts (`make db`, `make demo-reset`, `make passwords`) use `issue_passwords`: every
account gets its own password. `SEED_PASSWORD_<USERNAME>` (dots → underscores, upper case) sets one
account's password (kept, for scripts that sign in as that account); every other account gets a
random first password that it must change at first sign-in. No password is shared between accounts.

`seed` (one fixture password for every user) is for throwaway test and evaluation databases only:

    uv run python -m credassure.ledger.seed var/case-e2e.db --password-env E2E_PASSWORD

Passwords live only in the environment, the one-time hand-out file and as argon2 hashes in the
local DB, never in git. Existing usernames are left untouched unless re-issued, so `make db` is
idempotent.
"""

import argparse
import os
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

from credassure.security import password_policy
from credassure.security.auth import Role, hash_password

from . import migrate, reads, session, writes
from .models import User

MIN_PASSWORD = 12
USERS = Path(__file__).resolve().parents[5] / "data" / "frozen" / "v1" / "users" / "eval_users.yaml"


def env_key(username: str) -> str:
    return "SEED_PASSWORD_" + username.replace(".", "_").upper()


# No 0/O, 1/l/I: the hand-out file is read and typed by people.
_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"


def new_password() -> str:
    """A random first password: 4 groups of 4 (80 bits), e.g. k7pm-x3rt-9qzw-h2nd."""
    return "-".join("".join(secrets.choice(_ALPHABET) for _ in range(4)) for _ in range(4))


@dataclass(frozen=True)
class Issued:
    username: str
    role: str
    password: str
    temporary: bool  # True: generated here, changed at first sign-in; False: SEED_PASSWORD_<USER>


def _overrides(rows: list[dict[str, Any]], env: dict[str, str]) -> dict[str, str]:
    """The accounts whose password the operator set in the environment: each must pass the policy
    and differ from every other one (values are never echoed)."""
    out = {
        r["username"]: env[env_key(r["username"])] for r in rows if env.get(env_key(r["username"]))
    }
    bad = [
        f"{env_key(u)} ({'; '.join(found)})"
        for u, pw in out.items()
        if (found := password_policy.problems(pw, u))
    ]
    if bad:
        raise SystemExit("refused: " + ", ".join(bad))
    seen: dict[str, str] = {}
    for u, pw in sorted(out.items()):
        if pw in seen:
            raise SystemExit(
                f"{env_key(seen[pw])} and {env_key(u)} are the same: "
                "each account needs its own password"
            )
        seen[pw] = u
    return out


def issue_passwords(
    db: Path | str,
    env: dict[str, str],
    tenant_id: str = "default",
    users: Path = USERS,
    *,
    reissue: bool = False,
) -> list[Issued]:
    """Create missing accounts, each with its own password (ADR 0038 accounts).

    `reissue` also gives every existing seeded account of this tenant a new password, signs it out
    everywhere (token version bump) and audits PASSWORD_RESET; MFA enrolment is kept. A shared
    SEED_PASSWORD is never used here. Returns what was set, for the one-time hand-out file."""
    rows: list[dict[str, Any]] = yaml.safe_load(users.read_text(encoding="utf-8"))["users"]
    chosen = _overrides(rows, env)
    migrate.upgrade("case", db)
    engine = session.case_engine(db)
    issued: list[Issued] = []
    used: set[str] = set(chosen.values())
    try:
        with session.transaction(engine) as s:
            existing = {u.username: u for u in s.scalars(select(User))}
            for row in rows:
                name, role = row["username"], Role(row["role"]).value
                user = existing.get(name)
                if user is not None and not (reissue and user.tenant_id == tenant_id):
                    continue
                password = chosen.get(name)
                temporary = password is None
                while password is None or (temporary and password in used):
                    password = new_password()
                used.add(password)
                if user is None:
                    created = writes.add_user(
                        s,
                        user_id=f"u-{name}",
                        tenant_id=tenant_id,
                        username=name,
                        role=role,
                        emp_id=row.get("emp_id"),
                        password_hash=hash_password(password),
                    )
                    created.must_change_password = temporary
                else:
                    writes.update_user(
                        s,
                        user_id=user.id,
                        tenant_id=tenant_id,
                        actor="seed",
                        changes={
                            "password_hash": hash_password(password),
                            "must_change_password": temporary,
                        },
                        event_type="PASSWORD_RESET",
                        payload={"by": "seed", "reason": "make passwords"},
                        revoke=True,
                    )
                issued.append(Issued(name, role, password, temporary))
    finally:
        engine.dispose()
    return issued


def password_for(username: str, env: dict[str, str]) -> str | None:
    return env.get("SEED_PASSWORD_" + username.replace(".", "_").upper()) or env.get(
        "SEED_PASSWORD"
    )


def seed(
    db: Path | str, env: dict[str, str], tenant_id: str = "default", users: Path = USERS
) -> int:
    rows: list[dict[str, Any]] = yaml.safe_load(users.read_text(encoding="utf-8"))["users"]
    weak = [
        r["username"] for r in rows if len(password_for(r["username"], env) or "") < MIN_PASSWORD
    ]
    if weak:
        raise SystemExit(
            f"set SEED_PASSWORD (or SEED_PASSWORD_<USER>), {MIN_PASSWORD}+ characters, for: "
            + ", ".join(weak)
        )
    migrate.upgrade("case", db)
    engine = session.case_engine(db)
    added = 0
    with session.transaction(engine) as s:
        existing = set(s.scalars(select(User.username)))
        for row in rows:
            if row["username"] in existing:
                continue
            writes.add_user(
                s,
                user_id=f"u-{row['username']}",
                tenant_id=tenant_id,
                username=row["username"],
                role=Role(row["role"]).value,
                emp_id=row.get("emp_id"),
                password_hash=hash_password(password_for(row["username"], env) or ""),
            )
            added += 1
    engine.dispose()
    return added


def bootstrap_admin(
    db: Path | str, username: str, password: str, tenant_id: str = "default"
) -> str:
    """ADR 0038: the first user_admin of a tenant (the admin API needs an admin to exist). Refused
    when the tenant already has an active admin; the password must pass the policy and is changed
    at first sign-in, where MFA enrolment is also required."""
    found = password_policy.problems(password, username)
    if found:
        raise SystemExit("BOOTSTRAP_ADMIN_PASSWORD: " + "; ".join(found))
    migrate.upgrade("case", db)
    engine = session.case_engine(db)
    try:
        with session.transaction(engine) as s:
            if reads.active_admins(s, tenant_id):
                raise SystemExit(f"tenant {tenant_id} already has an active user_admin")
            user = writes.create_user(
                s,
                tenant_id=tenant_id,
                actor="bootstrap",
                username=username,
                role=Role.USER_ADMIN.value,
                password_hash=hash_password(password),
                display_name=username,
            )
            return user.id
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m credassure.ledger.seed")
    parser.add_argument("db", nargs="?", default="var/case.db")
    parser.add_argument("--users", type=Path, default=USERS, help="eval_users.yaml (S08/S19)")
    parser.add_argument(
        "--bootstrap-admin",
        metavar="USERNAME",
        help="create the first user_admin; password from BOOTSTRAP_ADMIN_PASSWORD (never argv)",
    )
    parser.add_argument(
        "--password-env",
        metavar="VAR",
        help="test databases only: every user signs in with the password in this variable",
    )
    args = parser.parse_args(argv)
    if args.bootstrap_admin:
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
        tenant = os.environ.get("TENANT_ID", "default")
        user_id = bootstrap_admin(args.db, args.bootstrap_admin, password, tenant)
        print(f"created user_admin {args.bootstrap_admin} ({user_id})", file=sys.stderr)
        return 0
    if not args.password_env:
        parser.error("the app database is seeded by `make db` (each account its own password)")
    password = os.environ.get(args.password_env, "")
    if len(password) < MIN_PASSWORD:
        parser.error(f"set {args.password_env} ({MIN_PASSWORD}+ characters) for this test database")
    tenant = os.environ.get("TENANT_ID", "default")
    added = seed(args.db, {"SEED_PASSWORD": password}, tenant_id=tenant, users=args.users)
    print(f"seeded {added} users into {args.db}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
