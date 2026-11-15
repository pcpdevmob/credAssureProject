"""Phase 9a: Onboarding agent through fake ports (ONB-01..05, BR-03/04, SUP-05)."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from credassure.agents.onboarding.agent import GO_TEXT, make_recheck, run
from credassure.core.enums import Decision, Stage
from credassure.core.ports import StageContext
from credassure.engines.onboarding_rules import evaluate
from credassure.llm.fake import FakeLLM

ROOT = Path(__file__).resolve().parents[3]
AS_OF = date(2026, 11, 15)
PROFILES = {
    p["emp_id"]: p for p in json.loads((ROOT / "data/frozen/v1/hr/profiles.json").read_text())
}
ITEMS = [
    item
    for item in map(json.loads, (ROOT / "evaluation/testset/v1/items.jsonl").open())
    if item["category"] == "onboarding"
]


class Ledger:
    def __init__(self) -> None:
        self.facts: dict[str, str] = {}

    def get(self, case_id: str, key: str) -> str | None:
        return self.facts.get(key)

    def put_fact(self, case_id: str, key: str, value: Decimal | int | str, **_: str) -> int:
        self.facts[key] = str(value)
        return 1


class Tools:
    """Handlers like the gateway's: the emp_id is bound to the case, never passed by the agent."""

    def __init__(self, emp_id: str | None) -> None:
        self.emp_id, self.calls = emp_id, []  # type: ignore[var-annotated]

    def call(self, name: str, case_id: str, args: Any = None) -> Any:
        self.calls.append(name)
        if name == "get_hr_profile":
            return PROFILES.get(self.emp_id or "")
        if name == "evaluate_onboarding_rules":
            return evaluate(args["profile"], AS_OF)
        raise AssertionError(f"tool {name} not allowed for onboarding")


class Clock:
    def today(self) -> date:
        return AS_OF


def ctx(emp_id: str | None, llm: Any = None, ledger: Ledger | None = None) -> StageContext:
    return StageContext(
        case_id="CA-2026-0101",
        tenant_id="default",
        stage=Stage("onboarding"),
        trace_id="t",
        ledger=ledger or Ledger(),
        tools=Tools(emp_id),
        llm=llm,
        clock=Clock(),
    )


def emp(item: dict[str, Any]) -> str:
    return "E" + item["input"]["actor"].split(".e")[1]


@pytest.mark.parametrize("item", ITEMS, ids=[i["id"] for i in ITEMS])
def test_ONB03_frozen_items_gate_and_failed_rules(item: dict[str, Any]) -> None:
    result = run(ctx(emp(item)))
    assert result.decision.value == item["gold"]["gate"]
    assert sorted(b.field for b in result.blockers) == item["gold"]["failed_rules"]


@pytest.mark.parametrize("item", ITEMS, ids=[i["id"] for i in ITEMS])
def test_ONB04_template_names_every_failed_rule(item: dict[str, Any]) -> None:
    result = run(ctx(emp(item)))
    for rule in item["gold"]["failed_rules"]:
        assert rule in (result.narrative or "")
    if not item["gold"]["failed_rules"]:
        assert result.narrative == GO_TEXT


def test_ONB04_model_reply_used_only_when_it_names_every_failed_rule() -> None:
    good = FakeLLM(
        {"onb_explain": "[FIN-101] has expired and [policy_ack] is missing; retake both."}
    )
    assert run(ctx("E020", good)).narrative.startswith("[FIN-101] has expired")  # type: ignore[union-attr]
    partial = FakeLLM({"onb_explain": "[FIN-101] has expired."})
    narrative = run(ctx("E020", partial)).narrative or ""
    assert "policy_ack" in narrative and narrative.startswith("Preparer readiness is blocked")


def test_ONB04_model_sees_only_the_rule_table_not_the_hr_record() -> None:
    llm = FakeLLM({"onb_explain": "FIN-101"})
    run(ctx("E009", llm))
    ((name, prompt),) = llm.calls
    assert name == "onb_explain"
    assert "Synthetic" not in prompt and "E009" not in prompt and "2026-" not in prompt


def test_ONB04_no_model_call_on_go() -> None:
    llm = FakeLLM()
    assert run(ctx("E001", llm)).decision is Decision.GO
    assert llm.calls == []


def test_ONB01_missing_hr_record_needs_input_with_one_question() -> None:
    result = run(ctx(None))
    assert result.decision is Decision.NEEDS_INPUT and result.question


def test_ONB03_needs_input_asks_one_focused_question() -> None:
    result = run(ctx("E012"))
    assert result.decision is Decision.NEEDS_INPUT
    assert result.question and "AML-201" in result.question


def test_ONB05_agent_uses_only_read_tools_and_writes_only_onb_facts() -> None:
    ledger = Ledger()
    c = ctx("E009", ledger=ledger)
    run(c)
    assert c.tools.calls == ["get_hr_profile", "evaluate_onboarding_rules"]  # type: ignore[attr-defined]
    assert all(k.startswith("onb.") for k in ledger.facts)
    assert ledger.facts["onb.rule.FIN-101"] == "FAIL" and ledger.facts["onb.gate"] == "NO_GO"


def test_SUP05_recheck_passes_on_honest_facts_and_flags_a_tampered_ledger() -> None:
    ledger = Ledger()
    result = run(ctx("E001", ledger=ledger))
    check = make_recheck(lambda _case: PROFILES["E001"], AS_OF)
    assert check(result, ledger) == []
    ledger.facts["onb.rule.FIN-101"] = "FAIL"
    assert [b.code.value for b in check(result, ledger)] == ["SUP_RECHECK_MISMATCH"]


def test_SUP05_recheck_blocks_a_forced_go_for_an_expired_profile() -> None:
    ledger = Ledger()
    forced = run(ctx("E001", ledger=ledger))  # GO facts, but HR now says E009
    failed = make_recheck(lambda _case: PROFILES["E009"], AS_OF)(forced, ledger)
    codes = {b.code.value for b in failed}
    assert "ONB_TRAINING_EXPIRED" in codes and "SUP_RECHECK_MISMATCH" in codes


def test_ONB04_bare_word_role_does_not_count_as_naming_the_role_rule() -> None:
    llm = FakeLLM({"onb_explain": "Your role is not authorised; ask an officer."})
    assert (run(ctx("E014", llm)).narrative or "").startswith("Preparer readiness is blocked")


def test_ONB04_model_numbers_or_dates_fall_back_to_template() -> None:
    llm = FakeLLM({"onb_explain": "[FIN-101] expired on 12 March; retake it within 7 days."})
    assert (run(ctx("E009", llm)).narrative or "").startswith("Preparer readiness is blocked")


def test_ONB04_model_timeout_keeps_the_code_gate_and_uses_the_template() -> None:
    from credassure.core.errors import LLMTimeout

    class Slow:
        def complete(self, prompt: str, **_: Any) -> str:
            raise LLMTimeout("no reply in 30 s")

    result = run(ctx("E009", Slow()))
    assert result.decision is Decision.NO_GO
    assert (result.narrative or "").startswith("Preparer readiness is blocked")


@pytest.mark.parametrize(
    "reply",
    [
        "[FIN-101] is fine. Decision: GO, approved.",
        "Once [FIN-101] is retaken we will accept the offer.",
        "[FIN-101] expired; [role] also needs review.",  # a rule that passed
    ],
)
def test_VER03_interim_guard_rejects_approval_wording_and_passed_rules(reply: str) -> None:
    result = run(ctx("E009", FakeLLM({"onb_explain": reply})))
    assert result.decision is Decision.NO_GO
    assert (result.narrative or "").startswith("Preparer readiness is blocked")


def test_VER03_guard_keeps_plain_go_in_a_sentence() -> None:
    reply = "Please go to the HR portal and retake [FIN-101]."
    assert run(ctx("E009", FakeLLM({"onb_explain": reply}))).narrative == reply
