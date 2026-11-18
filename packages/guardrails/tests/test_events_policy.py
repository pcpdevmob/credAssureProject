"""ADR 0029 §4 and §5 (scope #56): the policy file is versioned and hashed; events go to traces, and
only blocks, redactions, flags and caps reach the audit sink."""

from typing import Any

import pytest

from credassure.guardrails import events, policy
from credassure.observability.tracing import capture


def test_scope56_policy_file_matches_its_lock() -> None:
    assert policy.violations() == []
    assert policy.main(["check"]) == 0


def test_scope56_edit_without_bump_is_detected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    edited = tmp_path / "guardrails.yaml"
    edited.write_text(policy.POLICY.read_text() + "\n# tweak\n")
    monkeypatch.setattr(policy, "POLICY", edited)
    assert policy.violations() == ["guardrails.yaml changed without a version bump (was 1.0.0)"]
    bumped = tmp_path / "bumped.yaml"
    bumped.write_text(edited.read_text().replace("version: 1.0.0", "version: 1.0.1"))
    monkeypatch.setattr(policy, "POLICY", bumped)
    assert "not in guardrails.lock" in policy.violations()[0]


def test_scope56_pass_goes_to_trace_only_and_block_is_audited() -> None:
    audited: list[tuple[str, str, dict[str, Any]]] = []

    def sink(case_id: str, event_type: str, payload: dict[str, Any]) -> None:
        audited.append((case_id, event_type, payload))

    with capture() as spans:
        events.record("R3", "R3.tool_allowed", "pass", case_id="CA-1", audit=sink, tool="x")
        events.record("R3", "R3.loop_detected", "block", case_id="CA-1", audit=sink, tool="x")
    assert [s["action"] for s in spans if s["name"] == "guardrail"] == ["pass", "block"]
    assert [(c, t, p["rule_id"]) for c, t, p in audited] == [
        ("CA-1", "GUARDRAIL_EVENT", "R3.loop_detected")
    ]
    assert audited[0][2]["policy_version"] == policy.load().version


@pytest.mark.parametrize(
    ("rail", "rule", "action"),
    [
        ("R3", "R3.no_such_rule", "pass"),
        ("R1", "R3.tool_allowed", "pass"),
        ("R3", "R3.tool_allowed", "ignore"),
    ],
)
def test_scope56_unknown_rule_rail_or_action_fails_closed(
    rail: str, rule: str, action: str
) -> None:
    with pytest.raises(ValueError):
        events.record(rail, rule, action)


def test_scope56_policy_values_drive_the_rails() -> None:
    p = policy.load()
    assert p.excerpt_limit == 600 and p.full_text_bases == frozenset({"L1", "L2", "L5"})
    assert p.refuse_pii_kinds == frozenset({"AADHAAR", "PAN", "ACCOUNT"})
    assert "pass" not in p.audited_actions
