"""Stage timeout with cancellation (scope #23), template fallback (#48, ADR 0008), token budget
(SUP-07, NFR-03) and prompt versions on results and spans (#36)."""

import threading
from collections.abc import Callable, Mapping
from typing import Any

from credassure.core.blockers import BlockerCode
from credassure.core.budget import current_budget
from credassure.core.enums import Decision, Stage
from credassure.core.errors import BudgetExceeded, LLMTimeout, ModelUnavailable
from credassure.llm.fake import FakeLLM
from credassure.observability.tracing import capture

CASE = "CA-2026-0001"
Build = Callable[..., Any]


def _codes(outcome: Any, stage: Stage) -> list[str]:
    return [b.code for b in outcome.results[stage].blockers]


def test_scope23_hung_stage_times_out_saves_state_and_cancels_the_orphan(
    build: Build, make_agent: Build
) -> None:
    from credassure.agents.supervisor.graph import StageCancelledError

    release, refused = threading.Event(), threading.Event()

    def hang(ctx: Any) -> None:
        release.wait(5)
        try:
            ctx.ledger.put_fact(
                CASE, "wc.late", "1", unit="x", source_type="t", source_ref="r", produced_by="p"
            )
        except StageCancelledError:
            refused.set()

    wc = make_agent(Stage.WORKING_CAPITAL, on_call=hang)
    h = build(agents={Stage.WORKING_CAPITAL: wc}, stage_timeout=0.2)
    outcome = h.sup.run(CASE)
    assert outcome.results[Stage.WORKING_CAPITAL].decision is Decision.ERROR
    assert _codes(outcome, Stage.WORKING_CAPITAL) == [BlockerCode.SUP_TIMEOUT]
    assert "STAGE_TIMEOUT" in h.store.event_types()
    assert [r.stage for _, r in h.store.finished][-1] is Stage.WORKING_CAPITAL  # state saved
    assert Stage.LENDWISE not in outcome.results  # nothing ran after the timed-out stage
    release.set()
    assert refused.wait(5)  # the orphan thread could not write
    assert (CASE, "wc.late") not in h.ledger.facts


def test_scope23_orphan_tool_and_model_calls_are_refused(build: Build, make_agent: Build) -> None:
    from credassure.agents.supervisor.graph import StageCancelledError

    release, refused = threading.Event(), []

    def hang(ctx: Any) -> None:
        release.wait(5)
        for call in (lambda: ctx.tools.call("t", CASE), lambda: ctx.llm.complete("x")):
            try:
                call()
            except StageCancelledError:
                refused.append(1)

    done = threading.Event()
    wc = make_agent(Stage.WORKING_CAPITAL, on_call=lambda c: (hang(c), done.set()))
    h = build(agents={Stage.WORKING_CAPITAL: wc}, llm=FakeLLM(), stage_timeout=0.2)
    h.sup.run(CASE)
    release.set()
    assert done.wait(5)
    assert refused == [1, 1]


def test_scope23_model_call_timeout_is_a_TIMEOUT_blocker(build: Build, make_agent: Build) -> None:
    wc = make_agent(Stage.WORKING_CAPITAL, [LLMTimeout("30 s")])
    outcome = build(agents={Stage.WORKING_CAPITAL: wc}, llm=FakeLLM()).sup.run(CASE)
    (blocker,) = outcome.results[Stage.WORKING_CAPITAL].blockers
    assert blocker.code is BlockerCode.SUP_TIMEOUT
    assert blocker.message == "model call timed out"


def test_scope23_default_stage_timeout_is_five_minutes(build: Build) -> None:
    assert build().sup.stage_timeout == 300.0


class OpenCircuit(FakeLLM):
    circuit_state = "open"


def test_scope48_open_circuit_runs_the_stage_on_templates(build: Build, make_agent: Build) -> None:
    wc = make_agent(Stage.WORKING_CAPITAL)
    h = build(agents={Stage.WORKING_CAPITAL: wc}, llm=OpenCircuit())
    outcome = h.sup.run(CASE)
    assert outcome.results[Stage.WORKING_CAPITAL].decision is Decision.GO
    assert wc.contexts[0].llm is None
    fallbacks = [p for _, e, p in h.store.audits if e == "LLM_FALLBACK"]
    assert {p["reason"] for p in fallbacks} == {"circuit_open"}


def test_scope48_model_lost_mid_stage_reruns_it_on_templates(
    build: Build, make_agent: Build
) -> None:
    wc = make_agent(Stage.WORKING_CAPITAL, [ModelUnavailable("down"), Decision.GO])
    h = build(agents={Stage.WORKING_CAPITAL: wc}, llm=FakeLLM())
    outcome = h.sup.run(CASE)
    assert outcome.results[Stage.WORKING_CAPITAL].decision is Decision.GO
    assert wc.contexts[0].llm is not None and wc.contexts[1].llm is None
    assert ("LLM_FALLBACK" in h.store.event_types()) is True


class Charging(FakeLLM):
    def complete(
        self, prompt: str, *, name: str = "default", json_schema: Mapping[str, Any] | None = None
    ) -> str:
        budget = current_budget()
        assert budget is not None  # the stage budget reaches the worker thread
        budget.check()
        budget.used += 500
        return "ok"


def test_NFR03_model_tokens_reach_the_stage_result(build: Build, make_agent: Build) -> None:
    wc = make_agent(Stage.WORKING_CAPITAL, on_call=lambda c: c.llm.complete("x", name="sup_plan"))
    outcome = build(agents={Stage.WORKING_CAPITAL: wc}, llm=Charging()).sup.run(CASE)
    assert outcome.results[Stage.WORKING_CAPITAL].tokens_used == 500


def test_NFR03_spent_budget_is_a_budget_blocker(build: Build, make_agent: Build) -> None:
    wc = make_agent(Stage.WORKING_CAPITAL, [BudgetExceeded("spent")])
    outcome = build(agents={Stage.WORKING_CAPITAL: wc}, llm=FakeLLM()).sup.run(CASE)
    assert _codes(outcome, Stage.WORKING_CAPITAL) == [BlockerCode.SUP_BUDGET_EXCEEDED]


def test_scope36_prompt_version_on_result_and_span(build: Build, make_agent: Build) -> None:
    from credassure.core.prompts import prompt_version

    wc = make_agent(Stage.WORKING_CAPITAL, on_call=lambda c: c.llm.complete("x", name="sup_plan"))
    with capture() as spans:
        outcome = build(agents={Stage.WORKING_CAPITAL: wc}, llm=FakeLLM()).sup.run(CASE)
    version = prompt_version("sup_plan")
    assert outcome.results[Stage.WORKING_CAPITAL].prompt_versions == {"sup_plan": version}
    (llm,) = [s for s in spans if s["name"] == "llm"]
    assert llm["prompt_version"] == version and len(llm["prompt_sha"]) == 64


def test_NFR07_llm_span_carries_masked_io(build: Build, make_agent: Build) -> None:
    pan = "ABCPE1234F"
    wc = make_agent(Stage.WORKING_CAPITAL, on_call=lambda c: c.llm.complete(f"PAN {pan}"))
    with capture() as spans:
        build(agents={Stage.WORKING_CAPITAL: wc}, llm=FakeLLM(default=f"echo {pan}")).sup.run(CASE)
    (llm,) = [s for s in spans if s["name"] == "llm"]
    assert llm["input"] == "PAN [REDACTED_PAN]" and llm["output"] == "echo [REDACTED_PAN]"


class Down(FakeLLM):
    def complete(self, *a: Any, **k: Any) -> str:
        raise ModelUnavailable("down")


def test_scope48_planner_falls_back_to_the_fixed_plan(build: Build) -> None:
    plan = build(llm=Down(), planner_mode="llm_proposes").sup.plan(CASE)
    assert plan.mode == "fixed"
