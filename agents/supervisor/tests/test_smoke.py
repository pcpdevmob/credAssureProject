"""Smoke test for the supervisor agent (SUP-01)."""

from credassure.agents.supervisor.agent import version


def test_smoke_version() -> None:
    assert version() == "0.1.0"
