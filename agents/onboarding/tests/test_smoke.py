"""Smoke test for the onboarding agent (ONB-01)."""

from credassure.agents.onboarding.agent import version


def test_smoke_version() -> None:
    assert version() == "0.1.0"


def test_placeholder_onboarding_returns_a_go_result_with_and_without_llm() -> None:
    """Phase 8 skeleton: a real AgentResult; the LLM drafts only the narrative."""
    from datetime import date
    from decimal import Decimal
    from typing import Any

    from credassure.agents.onboarding.agent import TEMPLATE, run
    from credassure.core.enums import Decision, Stage
    from credassure.core.ports import StageContext
    from credassure.llm.fake import FakeLLM

    facts: dict[str, Any] = {}

    class Ledger:
        def get(self, case_id: str, key: str) -> str | None:
            return facts.get(key)

        def put_fact(self, case_id: str, key: str, value: Decimal | int | str, **_: str) -> int:
            facts[key] = str(value)
            return 1

    class Clock:
        def today(self) -> date:
            return date(2026, 11, 15)

    class Tools:
        def call(self, name: str, case_id: str, args: Any = None) -> Any:
            raise AssertionError("placeholder calls no tools")

    for llm in (None, FakeLLM(default="drafted")):
        ctx = StageContext(
            case_id="CA-2026-0001",
            tenant_id="default",
            stage=Stage("onboarding"),
            trace_id="t1",
            ledger=Ledger(),
            tools=Tools(),
            llm=llm,
            clock=Clock(),
        )
        result = run(ctx)
        assert result.decision is Decision.GO
        assert result.case_id == "CA-2026-0001"
        assert result.narrative == (TEMPLATE if llm is None else "drafted")
