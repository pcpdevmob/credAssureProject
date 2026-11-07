"""Supervisor graph (Phase 8a contract): SUP-01, 03..08, APR-01..03, scope #1 #4 #19.

Fakes live in conftest.py. Amounts are rupees as Decimal text; routing expectations are the
BRD §8.8 thresholds by hand (₹1,50,00,000), not computed by the engine under test.
"""

from collections.abc import Callable
from typing import Any

import pytest

from credassure.agents.supervisor.graph import RunOutcome, default_rechecks
from credassure.core.blockers import BlockerCode
from credassure.core.enums import AgentName, Decision, Stage
from credassure.core.plan import FIXED_STAGES
from credassure.core.results import AgentResult, Blocker, EvidenceRef
from credassure.llm.fake import FakeLLM
from credassure.observability.tracing import capture
from credassure.tools.runner import LoopDetected

CASE = "CA-2026-0001"  # same as conftest.CASE (importlib mode: conftest is not importable)
PLAN_STAGES = FIXED_STAGES

Build = Callable[..., Any]  # conftest.build -> Harness
MakeAgent = Callable[..., Any]  # conftest.make_agent -> ScriptedAgent
Ledger = Callable[..., Any]  # conftest.fake_ledger -> FakeLedger


def codes(outcome: RunOutcome, stage: Stage) -> set[BlockerCode]:
    return {b.code for b in outcome.results[stage].blockers}


def all_codes(outcome: RunOutcome) -> set[BlockerCode]:
    return {b.code for r in outcome.results.values() for b in r.blockers}


def _result(stage: Stage, decision: Decision = Decision.GO, **kw: Any) -> AgentResult:
    fields: dict[str, Any] = dict(
        agent=AgentName(stage.value),
        case_id=CASE,
        stage=stage,
        decision=decision,
        trace_id="t",
        agent_version="0.0.1-test",
    )
    fields.update(kw)
    return AgentResult(**fields)


# --- SUP-01 fixed plan, SUP-08 case injection -------------------------------------------------


def test_SUP01_stages_run_in_fixed_order_then_route(build: Build) -> None:
    h = build()
    outcome = h.sup.run(CASE)
    assert outcome.status == "AWAITING_APPROVAL"
    assert [stage for _, stage, _ in h.store.started] == [s.value for s in PLAN_STAGES]
    assert all(h.agents[s].calls == 1 for s in PLAN_STAGES)
    assert h.store.routes == [(CASE, "director_finance")]
    assert set(outcome.results) >= set(PLAN_STAGES)


def test_SUP01_every_stage_start_is_followed_by_its_finish(build: Build) -> None:
    h = build()
    h.sup.run(CASE)
    kinds = [c[0] for c in h.store.calls if c[0] in ("stage_started", "stage_finished")]
    assert kinds == ["stage_started", "stage_finished"] * len(PLAN_STAGES)


def test_SUP08_case_id_is_always_injected_into_the_stage_context(build: Build) -> None:
    h = build()
    h.sup.run(CASE)
    for stage in PLAN_STAGES:
        (ctx,) = h.agents[stage].contexts
        assert ctx.case_id == CASE
        assert ctx.stage == stage
        assert ctx.tenant_id == "default"
    assert {a.value for a in h.tools.requested} >= {s.value for s in PLAN_STAGES}
    assert all(case_id == CASE for case_id, _, _ in h.store.started)


# --- SUP-04 schema repair ----------------------------------------------------------------------


def test_SUP04_invalid_output_once_is_rerequested_and_accepted(
    build: Build, make_agent: MakeAgent
) -> None:
    wc = make_agent(Stage.WORKING_CAPITAL, ["not an AgentResult", Decision.GO])
    h = build(agents={Stage.WORKING_CAPITAL: wc})
    outcome = h.sup.run(CASE)
    assert wc.calls == 2
    assert outcome.results[Stage.WORKING_CAPITAL].decision == Decision.GO
    assert outcome.status == "AWAITING_APPROVAL"


def test_SUP04_result_for_another_case_counts_as_invalid(
    build: Build, make_agent: MakeAgent
) -> None:
    wrong = _result(Stage.WORKING_CAPITAL, case_id="CA-2026-0999")
    wc = make_agent(Stage.WORKING_CAPITAL, [wrong, Decision.GO])
    h = build(agents={Stage.WORKING_CAPITAL: wc})
    outcome = h.sup.run(CASE)
    assert wc.calls == 2
    assert outcome.results[Stage.WORKING_CAPITAL].case_id == CASE


def test_SUP04_invalid_output_three_times_ends_in_error(
    build: Build, make_agent: MakeAgent
) -> None:
    wc = make_agent(Stage.WORKING_CAPITAL, [{"decision": "MAYBE"}])
    h = build(agents={Stage.WORKING_CAPITAL: wc})
    outcome = h.sup.run(CASE)
    assert wc.calls == 3
    assert outcome.status == "FAILED"
    assert outcome.stage == Stage.WORKING_CAPITAL
    assert outcome.results[Stage.WORKING_CAPITAL].decision == Decision.ERROR
    assert BlockerCode.SUP_SCHEMA_INVALID in codes(outcome, Stage.WORKING_CAPITAL)
    assert h.agents[Stage.LENDWISE].calls == 0
    assert h.store.states[-1][1] == "FAILED"


# --- SUP-07 budgets, scope #4 loop detection ---------------------------------------------------


@pytest.mark.parametrize(("steps", "tokens"), [(11, 10), (1, 6001)])
def test_SUP07_step_or_token_cap_breach_fails_the_stage(
    build: Build, make_agent: MakeAgent, steps: int, tokens: int
) -> None:
    wc = make_agent(Stage.WORKING_CAPITAL, steps=steps, tokens=tokens)
    h = build(agents={Stage.WORKING_CAPITAL: wc})
    outcome = h.sup.run(CASE)
    assert outcome.status == "FAILED"
    assert outcome.stage == Stage.WORKING_CAPITAL
    assert outcome.results[Stage.WORKING_CAPITAL].decision == Decision.ERROR
    assert BlockerCode.SUP_BUDGET_EXCEEDED in codes(outcome, Stage.WORKING_CAPITAL)
    assert (CASE, "FAILED", Stage.WORKING_CAPITAL.value) in h.store.states
    assert h.agents[Stage.LENDWISE].calls == 0


def test_SUP07_exactly_at_the_caps_is_allowed(build: Build, make_agent: MakeAgent) -> None:
    wc = make_agent(Stage.WORKING_CAPITAL, steps=10, tokens=6000)
    h = build(agents={Stage.WORKING_CAPITAL: wc})
    assert h.sup.run(CASE).status == "AWAITING_APPROVAL"


def test_scope4_loop_detected_inside_an_agent_fails_the_stage(
    build: Build, make_agent: MakeAgent
) -> None:
    lw = make_agent(Stage.LENDWISE, [LoopDetected("price_offer repeated")])
    h = build(agents={Stage.LENDWISE: lw})
    outcome = h.sup.run(CASE)
    assert outcome.status == "FAILED"
    assert outcome.stage == Stage.LENDWISE
    blockers = outcome.results[Stage.LENDWISE].blockers
    assert any(
        b.code == BlockerCode.SUP_BUDGET_EXCEEDED and "loop" in b.message.lower() for b in blockers
    )
    assert h.agents[Stage.CRITIC].calls == 0


def test_SUP07_any_agent_exception_fails_the_stage(build: Build, make_agent: MakeAgent) -> None:
    lw = make_agent(Stage.LENDWISE, [RuntimeError("tool crashed")])
    h = build(agents={Stage.LENDWISE: lw})
    outcome = h.sup.run(CASE)
    assert outcome.status == "FAILED"
    assert outcome.results[Stage.LENDWISE].decision == Decision.ERROR
    assert h.store.states[-1][1] == "FAILED"


# --- SUP-05 deterministic re-check, scope #1 A4 ------------------------------------------------


def _failing_wc_recheck() -> dict[Stage, Any]:
    checks: dict[Stage, Any] = {s: (lambda _r, _l: []) for s in PLAN_STAGES}
    checks[Stage.WORKING_CAPITAL] = lambda _r, _l: [
        Blocker(code=BlockerCode.WC_CONFLICT_TOTALS, message="recompute differs")
    ]
    return checks


def test_SUP05_forced_go_is_overridden_by_failing_recheck(build: Build) -> None:
    h = build(rechecks=_failing_wc_recheck())
    outcome = h.sup.run(CASE)
    assert outcome.status == "PAUSED"
    assert outcome.stage == Stage.WORKING_CAPITAL
    assert outcome.results[Stage.WORKING_CAPITAL].decision == Decision.NO_GO
    assert BlockerCode.WC_CONFLICT_TOTALS in codes(outcome, Stage.WORKING_CAPITAL)
    assert any(c == CASE and e == "GATE_OVERRIDE" for c, e, _ in h.store.audits)
    assert h.agents[Stage.LENDWISE].calls == 0
    assert h.store.routes == []


def test_scope1_A4_skips_the_recheck(build: Build) -> None:
    h = build(rechecks=_failing_wc_recheck(), ablation="A4")
    outcome = h.sup.run(CASE)
    assert outcome.status == "AWAITING_APPROVAL"
    assert "GATE_OVERRIDE" not in h.store.event_types()


def test_SUP05_default_recheck_fails_a_go_carrying_a_gate_blocker(fake_ledger: Ledger) -> None:
    check = default_rechecks()[Stage.WORKING_CAPITAL]
    result = _result(
        Stage.WORKING_CAPITAL,
        blockers=[Blocker(code=BlockerCode.WC_DUPLICATE_ID, message="INV-7 twice")],
    )
    assert check(result, fake_ledger()) != []


def test_SUP05_default_recheck_ignores_a_warning_blocker(fake_ledger: Ledger) -> None:
    check = default_rechecks()[Stage.WORKING_CAPITAL]
    result = _result(
        Stage.WORKING_CAPITAL,
        blockers=[Blocker(code=BlockerCode.WC_MSE_PAYABLE_OVER_45D, message="payable > 45 d")],
    )
    assert check(result, fake_ledger()) == []


def test_SUP05_default_recheck_fails_on_missing_ledger_evidence(fake_ledger: Ledger) -> None:
    check = default_rechecks()[Stage.WORKING_CAPITAL]
    result = _result(
        Stage.WORKING_CAPITAL,
        evidence=[EvidenceRef(kind="ledger_fact", ref_id="wc.peak_shortfall")],
    )
    assert check(result, fake_ledger()) != []
    present = fake_ledger({(CASE, "wc.peak_shortfall"): "16200000"})
    assert check(result, present) == []


def test_SUP05_default_rechecks_cover_every_plan_stage() -> None:
    assert set(default_rechecks()) >= set(PLAN_STAGES)


def test_SUP05_default_recheck_overrides_go_in_the_graph(
    build: Build, make_agent: MakeAgent
) -> None:
    lw = make_agent(
        Stage.LENDWISE, evidence=[EvidenceRef(kind="ledger_fact", ref_id="lw.O1.v1.apr")]
    )
    h = build(agents={Stage.LENDWISE: lw})
    outcome = h.sup.run(CASE)
    assert outcome.status == "PAUSED"
    assert outcome.stage == Stage.LENDWISE
    assert outcome.results[Stage.LENDWISE].decision == Decision.NO_GO
    assert "GATE_OVERRIDE" in h.store.event_types()


# --- SUP-06 pause with one question, resume only the blocked stage -----------------------------


def test_SUP06_needs_input_pauses_with_one_question(build: Build, make_agent: MakeAgent) -> None:
    wc = make_agent(
        Stage.WORKING_CAPITAL,
        [Decision.NEEDS_INPUT, Decision.GO],
        question="What is the minimum cash buffer?",
    )
    h = build(agents={Stage.WORKING_CAPITAL: wc})
    outcome = h.sup.run(CASE)
    assert outcome.status == "PAUSED"
    assert outcome.stage == Stage.WORKING_CAPITAL
    assert outcome.question == "What is the minimum cash buffer?"
    assert h.store.states[-1] == (CASE, "PAUSED", Stage.WORKING_CAPITAL.value)
    assert h.agents[Stage.LENDWISE].calls == 0


def test_SUP06_question_falls_back_to_the_first_blocker_message(
    build: Build, make_agent: MakeAgent
) -> None:
    onb = make_agent(
        Stage.ONBOARDING,
        [Decision.NO_GO],
        blockers=[Blocker(code=BlockerCode.ONB_TRAINING_EXPIRED, message="AML-201 expired")],
    )
    outcome = build(agents={Stage.ONBOARDING: onb}).sup.run(CASE)
    assert outcome.status == "PAUSED"
    assert outcome.question == "AML-201 expired"


def test_SUP06_resume_reruns_only_the_blocked_stage(build: Build, make_agent: MakeAgent) -> None:
    wc = make_agent(Stage.WORKING_CAPITAL, [Decision.NEEDS_INPUT, Decision.GO], question="Buffer?")
    h = build(agents={Stage.WORKING_CAPITAL: wc})
    h.sup.run(CASE)
    outcome = h.sup.run(CASE)
    assert outcome.status == "AWAITING_APPROVAL"
    assert h.agents[Stage.ONBOARDING].calls == 1
    assert wc.calls == 2
    assert h.agents[Stage.LENDWISE].calls == 1
    assert h.agents[Stage.CRITIC].calls == 1


# --- SUP-03 upstream gates ---------------------------------------------------------------------


def test_SUP03_single_stage_run_with_upstream_not_go_is_blocked(
    build: Build, make_agent: MakeAgent
) -> None:
    wc = make_agent(
        Stage.WORKING_CAPITAL,
        [Decision.NO_GO],
        blockers=[Blocker(code=BlockerCode.WC_CONFLICT_TOTALS, message="totals differ")],
    )
    h = build(agents={Stage.WORKING_CAPITAL: wc})
    h.sup.run(CASE)
    outcome = h.sup.run(CASE, stage=Stage.LENDWISE)
    assert outcome.status == "PAUSED"
    assert outcome.stage == Stage.LENDWISE
    assert BlockerCode.SUP_UPSTREAM_NOT_GO in all_codes(outcome)
    assert h.agents[Stage.LENDWISE].calls == 0


def test_SUP03_single_stage_run_on_a_fresh_case_is_blocked(build: Build) -> None:
    h = build()
    outcome = h.sup.run(CASE, stage=Stage.CRITIC)
    assert outcome.status == "PAUSED"
    assert outcome.stage == Stage.CRITIC
    assert BlockerCode.SUP_UPSTREAM_NOT_GO in all_codes(outcome)
    assert h.agents[Stage.CRITIC].calls == 0


# --- APR-01..03 routing after Critic GO --------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "rule", "status", "route"),
    [
        ("14200000", "hold", "AWAITING_APPROVAL", "director_finance"),  # APR-02, demo case
        ("15000000", "hold", "HELD", "HELD"),  # APR-03 default
        ("15000000", "director", "AWAITING_APPROVAL", "director_finance"),  # APR-03
        ("15000000", "vp", "AWAITING_APPROVAL", "vp_finance"),  # APR-03
        ("15000001", "hold", "AWAITING_APPROVAL", "vp_finance"),  # APR-01
    ],
)
def test_APR01_03_route_from_recommended_amount(
    build: Build, amount: str, rule: str, status: str, route: str
) -> None:
    h = build(amount=amount, boundary_rule=rule)
    outcome = h.sup.run(CASE)
    assert outcome.status == status
    assert outcome.stage is None
    assert h.store.routes == [(CASE, route)]


def test_APR01_missing_recommended_amount_fails_closed(build: Build) -> None:
    h = build(amount=None)
    outcome = h.sup.run(CASE)
    assert outcome.status == "FAILED"
    assert h.store.routes == []


# --- APR-04/05 human decision through the interrupt --------------------------------------------


@pytest.mark.parametrize(("decision", "status"), [("approve", "APPROVED"), ("reject", "REJECTED")])
def test_APR04_decide_resumes_the_interrupt(build: Build, decision: str, status: str) -> None:
    h = build()
    h.sup.run(CASE)
    states_before = list(h.store.states)
    outcome = h.sup.decide(CASE, decision=decision)
    assert outcome.status == status
    assert h.store.states == states_before  # the ledger's record_decision owns the case status


def test_APR05_return_reopens_the_named_stage_only(build: Build) -> None:
    h = build()
    h.sup.run(CASE)
    returned = h.sup.decide(CASE, decision="return", return_stage=Stage.WORKING_CAPITAL)
    assert returned.status == "RETURNED"
    outcome = h.sup.run(CASE)
    assert outcome.status == "AWAITING_APPROVAL"
    assert h.agents[Stage.ONBOARDING].calls == 1
    assert h.agents[Stage.WORKING_CAPITAL].calls == 2
    assert h.agents[Stage.LENDWISE].calls == 2
    assert h.agents[Stage.CRITIC].calls == 2


# --- scope #19 visible plan --------------------------------------------------------------------


def _plan_span(spans: list[dict[str, Any]]) -> dict[str, Any]:
    (span,) = [s for s in spans if s["name"] == "plan"]
    return span


def test_scope19_fixed_plan_emits_an_accepted_plan_span(build: Build) -> None:
    h = build()
    with capture() as spans:
        plan = h.sup.plan(CASE)
    assert plan.case_id == CASE
    assert tuple(plan.stages) == FIXED_STAGES
    span = _plan_span(spans)
    assert span["case_id"] == CASE
    assert span["mode"] == "fixed"
    assert span["accepted"] is True
    assert list(span["stages"]) == list(FIXED_STAGES)


def test_scope19_llm_proposal_matching_the_fixed_order_is_accepted(build: Build) -> None:
    llm = FakeLLM(replies={"sup_plan": '["onboarding","working_capital","lendwise","critic"]'})
    h = build(llm=llm, planner_mode="llm_proposes")
    with capture() as spans:
        plan = h.sup.plan(CASE)
    assert [name for name, _ in llm.calls] == ["sup_plan"]
    assert tuple(plan.stages) == FIXED_STAGES
    assert plan.mode == "llm_proposes"
    assert _plan_span(spans)["accepted"] is True


@pytest.mark.parametrize(
    "reply",
    [
        '["onboarding","lendwise","working_capital","critic"]',  # reordered
        '["working_capital","lendwise","critic"]',  # skips onboarding (SUP-01)
        "first onboarding, then the rest",  # not JSON
    ],
)
def test_scope19_bad_llm_proposal_falls_back_to_fixed(build: Build, reply: str) -> None:
    h = build(llm=FakeLLM(replies={"sup_plan": reply}), planner_mode="llm_proposes")
    with capture() as spans:
        plan = h.sup.plan(CASE)
    assert tuple(plan.stages) == FIXED_STAGES
    assert plan.mode == "fixed"
    span = _plan_span(spans)
    assert span["accepted"] is False
    assert span["mode"] == "fixed"


def test_scope19_llm_proposes_without_a_model_falls_back_to_fixed(build: Build) -> None:
    h = build(llm=None, planner_mode="llm_proposes")
    with capture() as spans:
        plan = h.sup.plan(CASE)
    assert plan.mode == "fixed"
    assert _plan_span(spans)["accepted"] is False
