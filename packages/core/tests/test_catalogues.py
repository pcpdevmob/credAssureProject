"""Blocker catalogue and API error codes (scope #9, #32)."""

import pytest
from pydantic import ValidationError

from credassure.core.blockers import BlockerCode, BlockerEffect, blocker_effect
from credassure.core.enums import AgentName, Decision, Stage
from credassure.core.errors import ApiErrorCode
from credassure.core.findings import CriticFinding, FindingSeverity
from credassure.core.plan import FIXED_STAGES, Plan
from credassure.core.results import AgentResult, Blocker


def test_blocker_code_is_closed() -> None:
    assert BlockerCode.WC_MISSING_FIELD.value == "WC_MISSING_FIELD"
    assert blocker_effect(BlockerCode.WC_MISSING_FIELD) is BlockerEffect.GATE
    assert blocker_effect(BlockerCode.WC_MSE_PAYABLE_OVER_45D) is BlockerEffect.WARNING
    assert blocker_effect(BlockerCode.LW_RATE_MAY_RESET) is BlockerEffect.WARNING
    assert blocker_effect(BlockerCode.LW_BENCHMARK_NOT_EXTERNAL) is BlockerEffect.WARNING
    assert blocker_effect(BlockerCode.LW_CGTMSE_INELIGIBLE) is BlockerEffect.WARNING
    assert blocker_effect(BlockerCode.ONB_TRAINING_MISSING) is BlockerEffect.NEEDS_INPUT


def test_blocker_rejects_an_unknown_code() -> None:
    with pytest.raises(ValidationError):
        Blocker(code="NOT_A_REAL_CODE", message="no")  # type: ignore[arg-type]


def test_api_error_codes_are_stable_strings() -> None:
    assert ApiErrorCode.TOOL_NOT_ALLOWED.value == "TOOL_NOT_ALLOWED"
    assert ApiErrorCode.COLLECTION_NOT_ALLOWED.value == "COLLECTION_NOT_ALLOWED"
    assert ApiErrorCode.CASE_REQUIRED.value == "CASE_REQUIRED"
    assert ApiErrorCode.NOT_IMPLEMENTED.value == "NOT_IMPLEMENTED"


def test_plan_fixed_mode_uses_the_stage_order() -> None:
    plan = Plan(case_id="CA-2026-0001")
    assert plan.mode == "fixed"
    assert tuple(plan.stages) == FIXED_STAGES
    assert plan.schema_version == "1.0"


def test_plan_fixed_mode_rejects_a_reordered_list() -> None:
    with pytest.raises(ValidationError):
        Plan(case_id="CA-2026-0001", mode="fixed", stages=[Stage.CRITIC])


def test_critic_finding_records_severity_and_target_stage() -> None:
    finding = CriticFinding(
        severity=FindingSeverity.CRITICAL,
        code=BlockerCode.VER_UNMATCHED_NUMBER,
        message="₹1,42,00,000 is not in the ledger",
        span="₹1,42,00,000",
        target_stage=Stage.WORKING_CAPITAL,
    )
    assert finding.schema_version == "1.0"
    assert finding.severity is FindingSeverity.CRITICAL


def test_agent_result_still_round_trips_with_a_catalogue_blocker() -> None:
    result = AgentResult(
        agent=AgentName.WORKING_CAPITAL,
        case_id="CA-2026-0001",
        stage=Stage.WORKING_CAPITAL,
        decision=Decision.NEEDS_INPUT,
        blockers=[
            Blocker(
                code=BlockerCode.WC_MISSING_FIELD,
                message="min_cash_buffer",
                field="min_cash_buffer",
            )
        ],
        question="What is the minimum cash buffer?",
        trace_id="tr-1",
        agent_version="0.1.0",
    )
    assert AgentResult.model_validate_json(result.model_dump_json()) == result
