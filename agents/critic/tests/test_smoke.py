"""Smoke test for the critic agent (VER-01)."""

from credassure.agents.critic.agent import version


def test_smoke_version() -> None:
    assert version() == "0.1.0"
