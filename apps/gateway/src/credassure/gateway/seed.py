"""Seed the app's accounts (S08/S19), each with its own password (ADR 0038), never from code or git.

    uv run python -m credassure.gateway.seed             # make db: missing accounts only
    uv run python -m credassure.gateway.seed --reissue   # make passwords: new passwords for all

`SEED_PASSWORD_<USERNAME>` in the environment sets one account's password (scripts that sign in as
that account, e.g. safety_v2 or demo-reset). Every other account gets a random first password that
it changes at first sign-in. New passwords go to a hand-out file readable only by you
(`var/initial-passwords.txt`); they are never printed. A shared SEED_PASSWORD is not used.
Tests never use this module; they seed throwaway databases with their own fixture password.
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from credassure.gateway.settings import Settings, get_settings
from credassure.ledger.seed import Issued, issue_passwords

HANDOUT = "initial-passwords.txt"


def _where(settings: Settings) -> str:
    """Never print the URL: it carries the database password."""
    return "MySQL (CASE_DATABASE_URL)" if settings.case_database_url else str(settings.case_db)


def handout_path(settings: Settings) -> Path:
    return Path(settings.case_db).parent / HANDOUT


def write_handout(path: Path, issued: list[Issued], where: str, *, replace: bool = False) -> int:
    """Write the generated first passwords (mode 0600). Env-set passwords are not repeated here.

    New accounts are appended: the passwords already in the file still work. ``replace`` (make
    passwords: every seeded account has just been given a new one) starts the file again, so
    nobody copies an older password that no longer works (25 Nov)."""
    rows = [i for i in issued if i.temporary]
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = os.O_TRUNC if replace else os.O_APPEND
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | mode, 0o600)
    os.chmod(path, 0o600)  # an older file keeps its mode otherwise
    stamp = datetime.now(UTC).astimezone().strftime("%Y-%m-%d %H:%M %Z")
    width = max(len(i.username) for i in rows)
    lines = [
        f"# {stamp} · {where} · first passwords, one per account. Each is asked to change it at",
        "# first sign-in (approvers and admins then set up the authenticator app). Hand each one",
        "# to its owner only, then delete this file.",
        *(f"{i.username:<{width}}  {i.role:<17}  {i.password}" for i in rows),
        "",
    ]
    with os.fdopen(fd, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return len(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m credassure.gateway.seed")
    parser.add_argument(
        "--reissue",
        action="store_true",
        help="give every seeded account a new password (signs them out; MFA is kept)",
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    if os.environ.get("SEED_PASSWORD"):  # an older .env (uv run --env-file puts it in the env)
        print(
            "note: SEED_PASSWORD is no longer used (each account has its own password); "
            "remove it from .env",
            file=sys.stderr,
        )
    env = {k: v for k, v in os.environ.items() if k.startswith("SEED_PASSWORD_")}
    issued = issue_passwords(
        settings.case_target, env, tenant_id=settings.tenant_id, reissue=args.reissue
    )
    where = _where(settings)
    handed = write_handout(handout_path(settings), issued, where, replace=args.reissue)
    verb = "re-issued" if args.reissue else "created"
    print(f"{verb} {len(issued)} accounts in {where}", file=sys.stderr)
    if handed:
        print(
            f"{handed} first passwords (one per account, changed at first sign-in): "
            f"{handout_path(settings)}",
            file=sys.stderr,
        )
    if len(issued) > handed:
        print(f"{len(issued) - handed} set from SEED_PASSWORD_<USER>", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
