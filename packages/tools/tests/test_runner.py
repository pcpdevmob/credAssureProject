"""ToolRunner (Phase 8a): allowlist (scope #24), loop detection (scope #4), retries (SUP-07).

Allowlist facts come from agents/registry.yaml: lendwise may call audit_offer; it may not call
get_hr_profile (onboarding only).
"""

from typing import Any

import pytest

from credassure.core.enums import AgentName
from credassure.tools.registry import RegistryError
from credassure.tools.runner import LoopDetected, ToolError, ToolRunner

CASE = "CA-2026-0001"


def test_scope4_identical_repeat_call_raises_loop_detected() -> None:
    runner = ToolRunner(AgentName.LENDWISE, {"audit_offer": lambda **kw: "ok"})
    runner.call("audit_offer", CASE, {"offer_id": "O1", "version": 1})
    with pytest.raises(LoopDetected):
        runner.call("audit_offer", CASE, {"version": 1, "offer_id": "O1"})  # same args, reordered


def test_scope4_same_tool_with_different_args_is_fine() -> None:
    seen: list[dict[str, Any]] = []
    runner = ToolRunner(AgentName.LENDWISE, {"audit_offer": lambda **kw: seen.append(kw)})
    runner.call("audit_offer", CASE, {"offer_id": "O1"})
    runner.call("audit_offer", CASE, {"offer_id": "O2"})
    assert seen == [{"case_id": CASE, "offer_id": "O1"}, {"case_id": CASE, "offer_id": "O2"}]


def test_SUP08_handler_receives_the_case_id_and_returns_its_value() -> None:
    runner = ToolRunner("lendwise", {"audit_offer": lambda *, case_id: f"audited {case_id}"})
    assert runner.call("audit_offer", CASE) == f"audited {CASE}"


def test_scope24_tool_not_allowed_for_agent_raises_registry_error() -> None:
    called: list[str] = []
    runner = ToolRunner(AgentName.LENDWISE, {"get_hr_profile": lambda **kw: called.append("x")})
    with pytest.raises(RegistryError):
        runner.call("get_hr_profile", CASE)
    assert called == []


def test_SUP07_tool_error_is_retried_twice_then_raised() -> None:
    attempts: list[int] = []

    def flaky(**_: Any) -> None:
        attempts.append(1)
        raise ToolError("engine unavailable")

    runner = ToolRunner(AgentName.LENDWISE, {"price_offer": flaky})
    with pytest.raises(ToolError):
        runner.call("price_offer", CASE, {"offer_id": "O1"})
    assert len(attempts) == 3


def test_SUP07_success_on_second_attempt_returns_the_value() -> None:
    attempts: list[int] = []

    def once_flaky(**_: Any) -> str:
        attempts.append(1)
        if len(attempts) == 1:
            raise ToolError("transient")
        return "priced"

    runner = ToolRunner(AgentName.LENDWISE, {"price_offer": once_flaky})
    assert runner.call("price_offer", CASE, {"offer_id": "O1"}) == "priced"
    assert len(attempts) == 2
