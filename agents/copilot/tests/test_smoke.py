"""Smoke test for the copilot agent (CP-01)."""

from credassure.agents.copilot.agent import version


def test_smoke_version() -> None:
    assert version() == "0.1.0"
