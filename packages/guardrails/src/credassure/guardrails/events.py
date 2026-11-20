"""`guardrail_event` (ADR 0029 §5, scope #56): one record per guardrail decision.

Every event is a trace span named `guardrail` with `rail`, `rule_id`, `action` and `case_id`.
Blocks, redactions, flags and caps also go to the audit log as `GUARDRAIL_EVENT` when the caller
passes its audit sink; passes stay in traces only, so the hash chain is not flooded.
Payloads carry rule ids and counts only, never the text that triggered the rule.
"""

from collections.abc import Callable
from typing import Any

from credassure.observability.tracing import span

from .policy import ACTIONS, load

AuditSink = Callable[[str, str, dict[str, Any]], None]  # (case_id, event_type, payload)
EVENT_TYPE = "GUARDRAIL_EVENT"


def record(
    rail: str,
    rule_id: str,
    action: str,
    *,
    case_id: str | None = None,
    audit: AuditSink | None = None,
    **detail: Any,
) -> dict[str, Any]:
    """Emit one guardrail event and return its payload. Unknown rules or actions raise."""
    policy = load()
    if rule_id not in policy.rules or not rule_id.startswith(f"{rail}."):
        raise ValueError(f"unknown guardrail rule {rule_id!r} for rail {rail!r}")
    if action not in ACTIONS:
        raise ValueError(f"unknown guardrail action {action!r}")
    payload = {
        "rail": rail,
        "rule_id": rule_id,
        "action": action,
        "policy_version": policy.version,
        **detail,
    }
    with span("guardrail", case_id=case_id, **payload):
        pass
    if audit is not None and case_id and action in policy.audited_actions:
        audit(case_id, EVENT_TYPE, payload)
    return payload
