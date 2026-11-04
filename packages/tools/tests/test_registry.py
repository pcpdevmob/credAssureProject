"""Agent registry and data-access matrix (scope #24)."""

import pytest

from credassure.core.enums import AgentName
from credassure.core.errors import ApiErrorCode
from credassure.tools.registry import TOOL_NAMES, RegistryError, authorize, rules_from_allow


def test_registry_lists_the_thirteen_tools() -> None:
    assert len(TOOL_NAMES) == 13
    assert "get_hr_profile" in TOOL_NAMES
    assert "verify_claims" in TOOL_NAMES
    assert "route_proposal" in TOOL_NAMES
    assert "lender_send_template" in TOOL_NAMES


def test_onboarding_may_read_hr_and_policy() -> None:
    authorize(AgentName.ONBOARDING, "get_hr_profile")
    authorize(AgentName.ONBOARDING, "evaluate_onboarding_rules")
    authorize(AgentName.ONBOARDING, "search_knowledge", collection="policy")


def test_onboarding_may_not_price_an_offer() -> None:
    with pytest.raises(RegistryError) as caught:
        authorize(AgentName.ONBOARDING, "price_offer")
    assert caught.value.code is ApiErrorCode.TOOL_NOT_ALLOWED


def test_onboarding_may_not_search_the_public_corpus() -> None:
    with pytest.raises(RegistryError) as caught:
        authorize(AgentName.ONBOARDING, "search_knowledge", collection="public")
    assert caught.value.code is ApiErrorCode.COLLECTION_NOT_ALLOWED


def test_working_capital_may_validate_case_files() -> None:
    authorize(AgentName.WORKING_CAPITAL, "validate_case_files")
    authorize(AgentName.WORKING_CAPITAL, "compute_cash_table")
    authorize(AgentName.WORKING_CAPITAL, "compute_recommendation")


def test_lendwise_may_audit_and_read_same_case_kfs() -> None:
    authorize(AgentName.LENDWISE, "audit_offer")
    authorize(AgentName.LENDWISE, "search_knowledge", collection="kfs", case_id="CA-2026-0001")


def test_kfs_without_a_case_is_rejected() -> None:
    with pytest.raises(RegistryError) as caught:
        authorize(AgentName.COPILOT, "search_knowledge", collection="kfs")
    assert caught.value.code is ApiErrorCode.CASE_REQUIRED


def test_copilot_may_search_public_policy_and_faq() -> None:
    authorize(AgentName.COPILOT, "search_knowledge", collection="public")
    authorize(AgentName.COPILOT, "search_knowledge", collection="policy")
    authorize(AgentName.COPILOT, "search_knowledge", collection="faq")
    authorize(AgentName.COPILOT, "search_knowledge", collection="kfs", case_id="CA-2026-0001")


def test_critic_may_verify_claims() -> None:
    authorize(AgentName.CRITIC, "verify_claims")
    authorize(AgentName.CRITIC, "search_knowledge", collection="public")


def test_supervisor_may_route() -> None:
    authorize(AgentName.SUPERVISOR, "route_proposal")


def test_malformed_allow_rule_fails_closed() -> None:
    with pytest.raises(RegistryError) as caught:
        rules_from_allow({"onboarding": "yes"})
    assert caught.value.code is ApiErrorCode.VALIDATION_FAILED
    with pytest.raises(RegistryError):
        rules_from_allow({"copilot": {"collections": "public"}})
    with pytest.raises(RegistryError):
        rules_from_allow({"copilot": {"collections": ["kfs"], "same_case_collections": "kfs"}})


def test_unknown_tool_is_rejected() -> None:
    with pytest.raises(RegistryError) as caught:
        authorize(AgentName.SUPERVISOR, "accept_offer")
    assert caught.value.code is ApiErrorCode.TOOL_NOT_ALLOWED
