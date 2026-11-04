"""Smoke test for the lendwise agent (LW-01)."""

from credassure.agents.lendwise.agent import version


def test_smoke_version() -> None:
    assert version() == "0.1.0"
