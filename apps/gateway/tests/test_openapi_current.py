"""Scope #28 / ADR 0004: the committed openapi.json is exactly what the app serves (CI guard)."""

from pathlib import Path

from credassure.gateway.openapi import main

COMMITTED = Path(__file__).resolve().parents[3] / "openapi.json"


def test_scope28_committed_openapi_json_is_current(tmp_path: Path) -> None:
    fresh = tmp_path / "openapi.json"
    main(fresh)
    assert fresh.read_text(encoding="utf-8") == COMMITTED.read_text(encoding="utf-8"), (
        "openapi.json is stale: run `make openapi && make client` and commit both"
    )
