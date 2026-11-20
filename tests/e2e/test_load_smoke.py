"""Scope #35 (P7.4): concurrent cases do not collide (SQLite WAL, per-case run lock, limiter).
Timing targets are measured on the real model with `make load-smoke`; here only correctness."""

import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

_spec = importlib.util.spec_from_file_location(
    "load_smoke", Path(__file__).resolve().parents[2] / "scripts" / "load_smoke.py"
)
assert _spec and _spec.loader
load_smoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(load_smoke)


def test_scope35_concurrent_demo_cases_all_reach_the_gold_outcome(
    make_client: Callable[..., tuple[TestClient, Any]],
) -> None:
    client, _ = make_client(True, rate_limit="100000/minute")
    result = load_smoke.smoke(client, "fixture-password-123", 6)
    assert (result["ok"], result["errors"]) == (6, [])
    assert set(result["stage_p95_s"]) == {"onboarding", "working-capital", "lendwise"}
