"""Smoke test for the working-capital agent (WC-01)."""

from credassure.agents.working_capital.agent import version


def test_smoke_version() -> None:
    assert version() == "0.1.0"
