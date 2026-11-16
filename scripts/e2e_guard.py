"""Refuse to run the e2e stack against the demo database.

Called first by `make e2e-db` and `make run-api-e2e`, in the same environment the gateway will see.
Stdlib only: it must work before any settings (JWT secret, model URL) are configured.
Exit 0 = the resolved CASE_DB is not the demo database; exit 1 = refused.
"""

import os
import sys
from pathlib import Path

DEMO_DB = Path("var/case.db")  # the Settings default; the demo and the dev stack use it


def same_file(a: Path, b: Path) -> bool:
    if a.resolve() == b.resolve():  # catches ./var/../var/case.db and symlinked directories
        return True
    return a.exists() and b.exists() and os.path.samefile(a, b)  # catches hard links


def main() -> int:
    target = Path(os.environ.get("CASE_DB") or DEMO_DB)  # unset means the Settings default
    if same_file(target, DEMO_DB):
        print(
            f"refusing: CASE_DB resolves to the demo database ({DEMO_DB}). "
            "Use var/case-e2e.db (make e2e-db).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
