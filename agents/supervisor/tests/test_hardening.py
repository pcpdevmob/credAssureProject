"""Phase 8 review fixes: no exception text in user-visible blockers (NFR-07), and a run that
lost its lock stops before the next stage (ADR 0007 §4)."""

import logging
from collections.abc import Callable
from typing import Any

import pytest

from credassure.core.blockers import BlockerCode
from credassure.core.enums import Stage
from credassure.tools.runner import LoopDetected

CASE = "CA-2026-0001"


def test_NFR07_S3_blocker_carries_only_the_exception_type_and_a_stable_code(
    build: Callable[..., Any], make_agent: Callable[..., Any], caplog: pytest.LogCaptureFixture
) -> None:
    secret = "sqlite3.OperationalError at /srv/var/case.db SELECT secret PAN ABCDE1234F"
    lw = make_agent(Stage.LENDWISE, [RuntimeError(secret)])
    with caplog.at_level(logging.ERROR):
        outcome = build(agents={Stage.LENDWISE: lw}).sup.run(CASE)
    assert outcome.status == "FAILED"
    result = outcome.results[Stage.LENDWISE]
    (blocker,) = result.blockers
    assert blocker.code == BlockerCode.SUP_AGENT_ERROR
    assert blocker.message == "agent error: RuntimeError"
    # the full detail is logged with the trace id, never stored
    assert secret in caplog.text and result.trace_id in caplog.text


def test_NFR07_S3_loop_blocker_does_not_echo_tool_arguments(
    build: Callable[..., Any], make_agent: Callable[..., Any]
) -> None:
    lw = make_agent(Stage.LENDWISE, [LoopDetected("price_offer {'offer': 'SECRET-ARG'}")])
    outcome = build(agents={Stage.LENDWISE: lw}).sup.run(CASE)
    (blocker,) = outcome.results[Stage.LENDWISE].blockers
    assert blocker.code == BlockerCode.SUP_BUDGET_EXCEEDED
    assert blocker.message.startswith("loop")
    assert "SECRET-ARG" not in blocker.message and "price_offer" not in blocker.message


# --- S1: a return with no pending approval fails closed (APR-04/05) ---------------------------


def test_S1_return_without_pending_approval_fails_closed(build: Callable[..., Any]) -> None:
    from credassure.agents.supervisor.graph import NoPendingApproval

    h = build(agents={})
    assert h.sup.awaiting_decision(CASE) is False  # never ran: nothing to resume
    with pytest.raises(NoPendingApproval):
        h.sup.decide(CASE, decision="return", return_stage=Stage.WORKING_CAPITAL)
    assert h.store.states[-1][1] == "FAILED"
    (event,) = [p for _, e, p in h.store.audits if e == "RETURN_REJECTED"]
    assert event["code"] == BlockerCode.SUP_RETURN_NO_PENDING_APPROVAL
    (_, stored) = h.store.finished[-1]
    assert stored.blockers[0].code == BlockerCode.SUP_RETURN_NO_PENDING_APPROVAL
    assert not any(status == "RETURNED" for _, status, _ in h.store.states)


def test_S1_return_after_the_decision_was_applied_fails_closed(build: Callable[..., Any]) -> None:
    from credassure.agents.supervisor.graph import NoPendingApproval

    h = build()
    h.sup.run(CASE)
    assert h.sup.awaiting_decision(CASE) is True
    h.sup.decide(CASE, decision="approve")
    with pytest.raises(NoPendingApproval):
        h.sup.decide(CASE, decision="return", return_stage=Stage.LENDWISE)
    assert h.store.states[-1][1] == "FAILED"


# --- N1: unknown return stage is a validation error -------------------------------------------


@pytest.mark.parametrize("stage", [Stage.CRITIC, None])
def test_N1_unknown_or_missing_return_stage_raises(
    build: Callable[..., Any], stage: Stage | None
) -> None:
    from credassure.agents.supervisor.graph import InvalidReturnStageError

    h = build()
    h.sup.run(CASE)
    states = list(h.store.states)
    with pytest.raises(InvalidReturnStageError):
        h.sup.decide(CASE, decision="return", return_stage=stage)
    assert h.sup.awaiting_decision(CASE) is True  # still waiting at the interrupt
    assert h.store.states == states


# --- N2: a HELD route names SUP_ROUTE_HELD --------------------------------------------------


def test_N2_held_route_reports_SUP_ROUTE_HELD(build: Callable[..., Any]) -> None:
    h = build(amount="15000000", boundary_rule="hold")
    outcome = h.sup.run(CASE)
    assert outcome.status == "HELD"
    assert outcome.reason == BlockerCode.SUP_ROUTE_HELD
    assert h.store.route_reasons == [BlockerCode.SUP_ROUTE_HELD]


def test_N2_normal_route_has_no_reason(build: Callable[..., Any]) -> None:
    h = build()
    outcome = h.sup.run(CASE)
    assert outcome.reason is None
    assert h.store.route_reasons == [None]


def test_scope47_cancelled_run_stops_before_the_next_stage(
    build: Callable[..., Any],
) -> None:
    h = build()
    beats = iter([False, True])  # lock held for onboarding, lost before working capital
    outcome = h.sup.run(CASE, cancelled=lambda: next(beats, True))
    assert outcome.status == "ABANDONED"
    assert outcome.stage == Stage.WORKING_CAPITAL
    assert h.agents[Stage.ONBOARDING].calls == 1
    assert h.agents[Stage.WORKING_CAPITAL].calls == 0  # nothing written after the loss
