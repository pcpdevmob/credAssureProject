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

from credassure.security.auth import Role, hash_password

from . import migrate, session, writes
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m credassure.ledger.seed")
    parser.add_argument("db", nargs="?", default="var/case.db")
    parser.add_argument("--users", type=Path, default=USERS, help="eval_users.yaml (S08/S19)")
    args = parser.parse_args(argv)
    added = seed(args.db, dict(os.environ), users=args.users)
    print(f"seeded {added} users into {args.db}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
