"""The e2e stack must never start against the demo database (var/case.db)."""

# ruff: noqa: S603, S607  (fixed argv lists, no untrusted input; `make` is resolved from PATH)
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
GUARD = ROOT / "scripts" / "e2e_guard.py"


def guard(case_db: str | None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "CASE_DB"}
    if case_db is not None:
        env["CASE_DB"] = case_db
    return subprocess.run(
        [sys.executable, str(GUARD)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30
    )


@pytest.mark.parametrize(
    "value",
    [
        "var/case.db",
        "./var/case.db",
        "var/../var/case.db",
        str(ROOT / "var" / "case.db"),
        None,  # unset means the Settings default, which is the demo database
        "",
    ],
)
def test_refuses_every_spelling_of_the_demo_database(value: str | None) -> None:
    r = guard(value)
    assert r.returncode == 1
    assert "refusing: CASE_DB resolves to the demo database" in r.stderr


def test_allows_the_e2e_database() -> None:
    assert guard("var/case-e2e.db").returncode == 0


def test_refuses_a_symlink_to_the_demo_database(tmp_path: Path) -> None:
    link = tmp_path / "alias.db"
    link.symlink_to(ROOT / "var" / "case.db")
    assert guard(str(link)).returncode == 1


def test_make_run_api_e2e_refuses_before_starting_the_gateway() -> None:
    r = subprocess.run(
        ["make", "run-api-e2e", "E2E_DB=var/case.db"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )  # fmt: skip
    assert r.returncode != 0
    assert "refusing: CASE_DB resolves to the demo database" in r.stderr
    assert "Uvicorn running" not in r.stdout + r.stderr  # the guard stops make before uvicorn


def test_guard_runs_before_anything_destructive_in_e2e_db() -> None:
    """`make -n` prints without running: the guard must come before the rm of the database file."""
    r = subprocess.run(
        ["make", "-n", "e2e-db", "E2E_DB=var/case.db"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )  # fmt: skip
    lines = r.stdout.splitlines()
    guard_at = next(i for i, ln in enumerate(lines) if "e2e_guard.py" in ln)
    rm_at = next(i for i, ln in enumerate(lines) if ln.startswith("rm -f"))
    assert guard_at < rm_at
