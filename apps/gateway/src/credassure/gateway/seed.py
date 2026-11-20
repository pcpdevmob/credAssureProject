"""Seed demo users with SEED_PASSWORD from Settings (S08/S19), never from code or git.

    uv run python -m credassure.gateway.seed        # into CASE_DATABASE_URL, else CASE_DB

SEED_PASSWORD_<USERNAME> in the environment still overrides one user (ledger.seed).
Tests never use this module; they seed with their own fixture password.
"""

import os
import sys

from credassure.gateway.settings import Settings, get_settings
from credassure.ledger.seed import seed


def _where(settings: Settings) -> str:
    """Never print the URL: it carries the database password."""
    return "MySQL (CASE_DATABASE_URL)" if settings.case_database_url else str(settings.case_db)


def main() -> int:
    settings = get_settings()
    env = {k: v for k, v in os.environ.items() if k.startswith("SEED_PASSWORD_")}
    if settings.seed_password is not None:
        env["SEED_PASSWORD"] = settings.seed_password.get_secret_value()
    added = seed(settings.case_target, env, tenant_id=settings.tenant_id)
    print(f"seeded {added} users into {_where(settings)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
