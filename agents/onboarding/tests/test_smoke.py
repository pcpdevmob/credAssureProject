"""Smoke test for the onboarding agent (ONB-01)."""

from credassure.agents.onboarding.agent import version


def test_smoke_version() -> None:
    assert version() == "0.3.0"
