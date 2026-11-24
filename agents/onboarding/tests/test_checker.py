"""Onboarding 0.3.0 (design from PR #43, Mousita): the agent's own rule checker, cross-checked with
engines.onboarding_rules on every run; who fixes each blocker; per-record evidence; SUP-05 re-check
with the independent checker. ONB-02, ONB-03, ONB-04, SUP-05, BR-04, BR-11."""

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from credassure.agents.onboarding import checker, rules
from credassure.agents.onboarding.agent import GO_TEXT, make_recheck, run
from credassure.core.blockers import BlockerCode
from credassure.core.enums import Decision
from credassure.engines.onboarding_rules import Readiness, evaluate
from credassure.evaluation.gold import rules as gold_rules

from .test_agent import AS_OF, PROFILES, Ledger, Tools, ctx


def same(mine: checker.Check, engine: Readiness) -> bool:
    return (
        mine.gate == engine.gate
        and dict(mine.rules) == dict(engine.rules)
        and set(mine.blockers) == set(engine.blockers)
    )


# ---- the checker agrees with the engine and with the independent gold ---------------------------
@pytest.mark.parametrize("emp_id", sorted(PROFILES))
def test_ONB02_checker_matches_engine_and_gold_on_every_frozen_profile(emp_id: str) -> None:
    mine = checker.check(PROFILES[emp_id], AS_OF)
    assert same(mine, evaluate(PROFILES[emp_id], AS_OF)), emp_id
    gold = gold_rules.onboarding(emp_id)
    assert (mine.gate, dict(mine.rules)) == (gold["gate"], gold["rules"])


def test_ONB02_checker_does_not_import_the_engine() -> None:
    """Two implementations of one rule book: the checker shares no code with the engine."""
    import ast

    tree = ast.parse(Path(checker.__file__).read_text(encoding="utf-8"))
    imported = [
        n.module or "" if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
        for a in n.names
    ]
    assert imported and not [m for m in imported if "engines" in m]


_DAY = st.integers(min_value=-400, max_value=400).map(lambda d: AS_OF + timedelta(days=d))
_TRAINING = st.fixed_dictionaries(
    {
        "code": st.sampled_from([*rules.MANDATORY, "OPS-110"]),
        "status": st.sampled_from(["completed", "in_progress", "not_started", ""]),
        "expires_on": st.one_of(st.none(), st.just(""), _DAY.map(date.isoformat)),
    }
)
_PROFILE = st.fixed_dictionaries(
    {
        "emp_id": st.just("E999"),
        "role": st.sampled_from(
            ["credit_proposal_officer", "senior_finance_analyst", "finance_analyst", "", "x"]
        ),
        "trainings": st.lists(_TRAINING, max_size=6),  # duplicates of one course included
        "policy_ack_version": st.sampled_from([None, "", "v1", "v2", "v3", "V3"]),
    }
)


@settings(max_examples=400, deadline=None)
@given(profile=_PROFILE, as_of=_DAY)
def test_ONB02_checker_matches_engine_on_generated_profiles(
    profile: dict[str, Any], as_of: date
) -> None:
    assert same(checker.check(profile, as_of), evaluate(profile, as_of))


# ---- disagreement stops the stage ------------------------------------------------------------
class LyingEngine(Tools):
    """The engine tool says GO for E009 (whose FIN-101 expired): a drift between the two checks."""

    def call(self, name: str, case_id: str, args: Any = None) -> Any:
        if name == "evaluate_onboarding_rules":
            go = evaluate(PROFILES["E001"], AS_OF)
            return Readiness(go.gate, dict(go.rules), go.blockers)
        return super().call(name, case_id, args)


def test_SUP05_engine_and_checker_disagree_gives_error_never_go() -> None:
    ledger = Ledger()
    c = ctx("E009", ledger=ledger)
    c = type(c)(**{**c.__dict__, "tools": LyingEngine("E009")})
    result = run(c)
    assert result.decision is Decision.ERROR
    assert [b.code for b in result.blockers] == [BlockerCode.SUP_RECHECK_MISMATCH]
    assert "FIN-101" in result.blockers[0].message and "gate" in result.blockers[0].message
    assert not [k for k in ledger.facts if k.startswith("onb.rule.") or k == "onb.gate"]
    assert "could not be confirmed" in (result.narrative or "")


# ---- who fixes it -------------------------------------------------------------------------------
WHO = {
    BlockerCode.ONB_ROLE_NOT_AUTHORISED: "your manager",
    BlockerCode.ONB_TRAINING_EXPIRED: "you",
    BlockerCode.ONB_TRAINING_INCOMPLETE: "you",
    BlockerCode.ONB_TRAINING_MISSING: "HR",
    BlockerCode.ONB_ACK_MISSING: "you",
    BlockerCode.ONB_ACK_OLD_VERSION: "you",
}


def test_ONB04_rule_book_names_who_fixes_every_onboarding_blocker() -> None:
    assert {code: text.who for code, text in rules.BLOCKERS.items()} == WHO


@pytest.mark.parametrize("emp_id", sorted(PROFILES))
def test_ONB04_every_blocker_says_who_fixes_it_and_the_template_too(emp_id: str) -> None:
    result = run(ctx(emp_id))
    for b in result.blockers:
        who = WHO[b.code]
        assert (b.next_action or "").endswith(f"Who fixes it: {who}."), b
        assert f"Who fixes it: {who}." in (result.narrative or "")


def test_ONB01_missing_hr_record_is_for_hr_to_fix() -> None:
    result = run(ctx(None))
    assert (result.blockers[0].next_action or "").endswith("Who fixes it: HR.")


def test_ONB04_model_slots_carry_the_action_without_the_who_line() -> None:
    from credassure.llm.fake import FakeLLM

    draft = (
        "Your {rule.FIN-101} has expired; {next.FIN-101}. And {rule.policy_ack}: {next.policy_ack}."
    )
    narrative = run(ctx("E020", FakeLLM({"onb_explain": draft}))).narrative or ""
    assert "Who fixes it" not in narrative and "retake the course" in narrative


# ---- per-record evidence ----------------------------------------------------------------------
class RefLedger(Ledger):
    def __init__(self) -> None:
        super().__init__()
        self.refs: dict[str, str] = {}

    def put_fact(self, case_id: str, key: str, value: Any, **kw: str) -> int:
        self.refs[key] = kw["source_ref"]
        return super().put_fact(case_id, key, value)


@pytest.mark.parametrize("emp_id", sorted(PROFILES))
def test_ONB01_each_rule_fact_cites_its_own_hr_record(emp_id: str) -> None:
    ledger = RefLedger()
    run(ctx(emp_id, ledger=ledger))
    want = {"role": f"hr.db:employees:{emp_id}"} | {
        code: f"hr.db:training_records:{emp_id}/{code}" for code in rules.MANDATORY
    }
    want["policy_ack"] = f"hr.db:policy_acknowledgements:{emp_id}/WC-POL"
    rule_refs = {k.removeprefix("onb.rule."): v for k, v in ledger.refs.items() if ".rule." in k}
    assert rule_refs and rule_refs == {r: want[r] for r in rule_refs}
    assert ledger.refs["onb.gate"] == f"hr.db:employees:{emp_id}"
    assert all("," not in ref for ref in ledger.refs.values())  # lineage splits refs on commas


# ---- SUP-05 with the independent checker ------------------------------------------------------
def test_SUP05_recheck_uses_the_checker_not_the_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = Ledger()
    result = run(ctx("E001", ledger=ledger))
    import credassure.engines.onboarding_rules as engine

    def broken(*_: Any, **__: Any) -> Readiness:
        raise AssertionError("the re-check must not call the engine")

    monkeypatch.setattr(engine, "evaluate", broken)
    check = make_recheck(lambda _case: PROFILES["E001"], AS_OF)
    assert check(result, ledger) == []
    failed = make_recheck(lambda _case: PROFILES["E009"], AS_OF)(result, ledger)
    assert {b.code for b in failed} >= {
        BlockerCode.ONB_TRAINING_EXPIRED,
        BlockerCode.SUP_RECHECK_MISMATCH,
    }


# ---- template -----------------------------------------------------------------------------------
def test_ONB04_go_text_names_no_figure_and_the_blocked_template_keeps_its_opening() -> None:
    assert not any(ch.isdigit() for ch in GO_TEXT)
    blocked = run(ctx("E009")).narrative or ""
    assert blocked.startswith("Preparer readiness is blocked")
    assert blocked.rstrip().endswith("run the preparer check again.")
