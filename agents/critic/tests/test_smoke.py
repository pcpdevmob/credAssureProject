"""The Critic stage (VER-01..05, ARCHITECTURE §6.3): re-verifies every recorded narrative and the
negotiation message against the current ledger; findings name the stage to reopen."""

import json
from datetime import date
from decimal import Decimal
from typing import Any

from credassure.agents.critic.agent import FINDINGS_KEY, run, version
from credassure.agents.critic.verify import Fact, verify
from credassure.core.enums import Decision, Stage
from credassure.core.ports import StageContext

CASE = "CA-2026-0001"


def test_smoke_version() -> None:
    assert version() == "0.2.0"


class Ledger:
    def __init__(self, facts: dict[str, str]) -> None:
        self.facts = dict(facts)

    def get(self, case_id: str, key: str) -> str | None:
        return self.facts.get(key)

    def put_fact(self, case_id: str, key: str, value: Decimal | int | str, **_: Any) -> int:
        self.facts[key] = str(value)
        return 1


class Clock:
    def today(self) -> date:
        return date(2026, 11, 15)


class Tools:
    """verify_claims over the ledger's facts, as the gateway wires it (all INR for the test)."""

    def __init__(self, ledger: Ledger) -> None:
        self.ledger, self.calls = ledger, 0

    def call(self, name: str, case_id: str, args: Any = None) -> Any:
        assert name == "verify_claims" and case_id == CASE
        self.calls += 1
        facts = {k: Fact(v, "INR") for k, v in self.ledger.facts.items() if v[:1].isdigit()}
        if args.get("keys") is not None:
            facts = {k: v for k, v in facts.items() if k in args["keys"]}
        return verify(
            args["text"],
            facts=facts,
            slots=args.get("slots"),
            model=args.get("model", False),
            stage=Stage(args["stage"]) if args["stage"] else None,
        )


def stage(facts: dict[str, str], ablation: str | None = None) -> tuple[Any, Ledger, Tools]:
    ledger = Ledger(facts)
    tools = Tools(ledger)
    ctx = StageContext(
        case_id=CASE,
        tenant_id="default",
        stage=Stage.CRITIC,
        trace_id="t1",
        ledger=ledger,
        tools=tools,
        llm=None,
        clock=Clock(),
        ablation=ablation,
    )
    return run(ctx), ledger, tools


def narrative(text: str, *, model: bool = False, slots: dict[str, str] | None = None) -> str:
    return json.dumps(
        {"source": "model" if model else "template", "slots": slots or {}, "text": text}
    )


GOOD = {
    "wc.recommended_amount": "14200000",
    "wc.narrative": narrative("The recommended facility is ₹1,42,00,000."),
    "lw.narrative": narrative("OF-01-B ranks first.", model=True, slots={"rank1.offer": "OF-01-B"}),
}


def test_VER01_clean_narratives_pass_and_findings_are_recorded() -> None:
    result, ledger, tools = stage(GOOD)
    assert result.decision is Decision.GO and tools.calls == 2
    assert json.loads(ledger.facts[FINDINGS_KEY]) == []


def test_VER01_ARCH63_a_narrative_that_disagrees_with_the_ledger_reopens_its_stage() -> None:
    forged = GOOD | {
        "lw.narrative": narrative(
            "OF-01-B ranks first because it is flexible.",
            model=True,
            slots={"rank1.offer": "OF-01-B"},
        )
    }
    result, ledger, _ = stage(forged)
    assert result.decision is Decision.NO_GO
    assert [(b.code.value, b.field) for b in result.blockers] == [
        ("VER_UNSUPPORTED_REASON", "lendwise")
    ]
    assert json.loads(ledger.facts[FINDINGS_KEY])[0]["target_stage"] == "lendwise"


def test_VER01_stale_amount_after_a_change_is_caught() -> None:
    stale = GOOD | {"wc.recommended_amount": "15000000"}
    result, _, _ = stage(stale)
    assert result.decision is Decision.NO_GO
    assert [b.field for b in result.blockers] == ["working_capital"]


def test_VER03_negotiation_message_is_rechecked() -> None:
    sent = GOOD | {
        "lw.negotiation.status": "sent",
        "lw.negotiation.current_fee": "50000",
        "lw.negotiation.message": "Its fee is ₹50,000. We accept your terms.",
    }
    result, _, tools = stage(sent)
    assert tools.calls == 3 and result.decision is Decision.NO_GO
    assert "VER_BANNED_CONTENT" in [b.code.value for b in result.blockers]
    assert all(b.field is None for b in result.blockers)  # pauses; a re-run cannot fix it


def test_scope1_A2_switches_the_critic_stage_off() -> None:
    result, _, tools = stage(GOOD | {"wc.recommended_amount": "1"}, ablation="A2")
    assert result.decision is Decision.GO and tools.calls == 0
