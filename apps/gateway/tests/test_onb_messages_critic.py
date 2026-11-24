"""Onboarding 0.3.0: every readiness message the agent can write passes the real Critic (VER-01/03)
with no ledger figure to lean on, for every frozen HR profile. ONB-04, VER-01, VER-03.
In the gateway's tests because it needs two agents (the agents never import each other)."""

import json
from datetime import date
from pathlib import Path

import pytest

from credassure.agents.critic.verify import verify
from credassure.agents.onboarding import agent, checker
from credassure.core.enums import Stage

ROOT = Path(__file__).resolve().parents[3]
AS_OF = date(2026, 11, 15)
PROFILES = json.loads((ROOT / "data/frozen/v1/hr/profiles.json").read_text(encoding="utf-8"))


def clean(text: str, slots: dict[str, str] | None = None) -> list[str]:
    found = verify(text, facts={}, slots=slots or {}, model=False, stage=Stage.ONBOARDING)
    return [f"{f.code}: {f.message}" for f in found]


@pytest.mark.parametrize("profile", PROFILES, ids=[p["emp_id"] for p in PROFILES])
def test_ONB04_VER03_readiness_message_passes_the_critic(profile: dict[str, object]) -> None:
    blockers = agent._blockers(checker.check(profile, AS_OF).blockers)
    text = agent.template(blockers)
    assert clean(text, agent.narrative_slots(blockers)) == [], text


def test_VER03_go_and_stop_messages_pass_the_critic() -> None:
    assert clean(agent.GO_TEXT) == []
    assert clean(f"{agent.MISMATCH}\nWho fixes it: the evaluator. Next: check the record.") == []
