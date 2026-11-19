"""Seed users into case.db (S08 demo users + S19 eval preparers). Kept apart from migrations (#29).

    SEED_PASSWORD=... uv run python -m credassure.ledger.seed var/case.db

A per-user SEED_PASSWORD_<USERNAME> (dots → underscores, upper case) wins over SEED_PASSWORD.
Passwords live only in the environment and as argon2 hashes in the local DB, never in git.
Existing usernames are left untouched, so the seed is idempotent.
"""

import argparse
import os
import sys
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
    args = parser.parse_args(argv)
    if args.bootstrap_admin:
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
        tenant = os.environ.get("TENANT_ID", "default")
        user_id = bootstrap_admin(args.db, args.bootstrap_admin, password, tenant)
        print(f"created user_admin {args.bootstrap_admin} ({user_id})", file=sys.stderr)
        return 0
    added = seed(args.db, dict(os.environ), users=args.users)
    print(f"seeded {added} users into {args.db}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
