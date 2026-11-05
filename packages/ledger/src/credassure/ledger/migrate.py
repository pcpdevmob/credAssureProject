"""Alembic migrations for case.db and corpus.db (scope #29). Seeds are separate (seed.py).

uv run python -m credassure.ledger.migrate upgrade case var/case.db
uv run python -m credassure.ledger.migrate downgrade corpus var/corpus.db
uv run python -m credassure.ledger.migrate revision case "add x"   # autogenerate from models
"""

import argparse
import tempfile
from pathlib import Path
from typing import Literal

from alembic import command
from alembic.config import Config

from .session import case_engine

Which = Literal["case", "corpus"]
HERE = Path(__file__).parent / "migrations"


def _run(which: str, db: Path | str, action: str, *args: str, **kwargs: object) -> None:
    if which not in ("case", "corpus"):
        raise ValueError("which must be 'case' or 'corpus'")
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    config = Config()
    config.set_main_option("script_location", str(HERE / which))
    engine = case_engine(db)  # same pragmas (WAL, busy timeout, foreign keys) as the app
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            getattr(command, action)(config, *args, **kwargs)
    finally:
        engine.dispose()


def upgrade(which: str, db: Path | str, target: str = "head") -> None:
    _run(which, db, "upgrade", target)


def downgrade(which: str, db: Path | str, target: str = "base") -> None:
    _run(which, db, "downgrade", target)


def revision(which: str, message: str) -> None:
    """Autogenerate the next revision by diffing the models against a scratch DB at head."""
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / f"{which}.db"
        upgrade(which, scratch)
        _run(which, scratch, "revision", message=message, autogenerate=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m credassure.ledger.migrate")
    parser.add_argument("action", choices=["upgrade", "downgrade", "revision"])
    parser.add_argument("which", choices=["case", "corpus"])
    parser.add_argument("arg", help="database path, or the message for 'revision'")
    args = parser.parse_args(argv)
    if args.action == "revision":
        revision(args.which, args.arg)
    else:
        (upgrade if args.action == "upgrade" else downgrade)(args.which, args.arg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
