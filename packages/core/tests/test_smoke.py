"""Core contract smoke test (design-detail §2.1, scope #25, #27, #46)."""

from credassure.core.enums import AgentName, Decision, Stage
from credassure.core.ports import UnavailableSupervisor
from credassure.core.results import AgentResult


def test_agent_result_round_trip() -> None:
    result = AgentResult(
        agent=AgentName.ONBOARDING,
        case_id="CA-2026-0001",
        stage=Stage.ONBOARDING,
        tenant_id="default",
        decision=Decision.NO_GO,
        trace_id="tr-1",
        agent_version="0.1.0",
    )
    assert AgentResult.model_validate_json(result.model_dump_json()) == result


def test_supervisor_port_is_unavailable() -> None:
    try:
        UnavailableSupervisor().run_stage("CA-2026-0001", "onboarding")
    except NotImplementedError as exc:
        assert "not implemented" in str(exc)
    else:
        raise AssertionError("expected NotImplementedError")
