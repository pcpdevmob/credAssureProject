"""BRD §14: every case run is one trace — plan, stages, route and the decision share one id."""

from collections.abc import Callable
from typing import Any

from credassure.core.enums import Stage
from credassure.observability.tracing import capture

CASE = "CA-2026-0001"


def test_OBJ08_one_trace_id_per_run_across_plan_stages_route_and_decision(
    build: Callable[..., Any],
) -> None:
    h = build()
    with capture() as spans:
        outcome = h.sup.run(CASE)
        h.sup.decide(CASE, decision="approve")
    names = [s["name"] for s in spans]
    assert names[0] == "plan" and "route" in names and names[-1] == "decision"
    assert names.count("stage") == 4
    trace_ids = {s["trace_id"] for s in spans}
    assert len(trace_ids) == 1  # one trace for the whole run and its approval
    (trace_id,) = trace_ids
    assert len(trace_id) == 32 and int(trace_id, 16) >= 0  # Langfuse / W3C trace id format
    assert {r.trace_id for r in outcome.results.values()} == {trace_id}
    assert set(outcome.results) == {
        Stage.ONBOARDING,
        Stage.WORKING_CAPITAL,
        Stage.LENDWISE,
        Stage.CRITIC,
    }


def test_OBJ08_a_new_run_starts_a_new_trace(build: Callable[..., Any]) -> None:
    h = build(amount=None)  # routing fails closed, so the case can run again
    with capture() as spans:
        h.sup.run(CASE)
        h.sup.run(CASE)
    plans = [s["trace_id"] for s in spans if s["name"] == "plan"]
    assert len(plans) == 2 and plans[0] != plans[1]


def test_E11_M1_M2_model_and_tool_calls_have_spans_in_the_run_trace(
    build: Callable[..., Any], make_agent: Callable[..., Any]
) -> None:
    from credassure.llm.fake import FakeLLM

    def work(ctx: Any) -> None:
        ctx.llm.complete("explain", name="wc_explain")
        ctx.tools.call("compute_cash_table", ctx.case_id, {"weeks": 26})

    wc = make_agent(Stage.WORKING_CAPITAL, on_call=work)
    h = build(agents={Stage.WORKING_CAPITAL: wc}, llm=FakeLLM())
    with capture() as spans:
        outcome = h.sup.run(CASE)
    trace_id = outcome.results[Stage.WORKING_CAPITAL].trace_id
    (llm,) = [s for s in spans if s["name"] == "llm"]
    assert llm["prompt"] == "wc_explain" and llm["trace_id"] == trace_id
    assert llm["stage"] == "working_capital"
    (tool,) = [s for s in spans if s["name"] == "tool"]
    assert tool["tool"] == "compute_cash_table" and tool["trace_id"] == trace_id
    (event,) = [p for _, e, p in h.store.audits if e == "TOOL_CALLED"]
    assert event == {
        "agent": "working_capital",
        "tool": "compute_cash_table",
        "trace_id": trace_id,
        "error": None,
    }


def test_E11_S1_plan_model_call_runs_inside_the_plan_span(build: Callable[..., Any]) -> None:
    from credassure.llm.fake import FakeLLM

    llm = FakeLLM(replies={"sup_plan": '["onboarding","working_capital","lendwise","critic"]'})
    h = build(llm=llm, planner_mode="llm_proposes")
    with capture() as spans:
        h.sup.plan(CASE, trace_id="a" * 32)
    assert [s["name"] for s in spans] == ["plan", "llm"]
    assert spans[1]["trace_id"] == "a" * 32
