"""The agent's own readiness checker (ONB-02, ONB-03, BR-04). Pure code, no model.

A second, separate implementation of the rule book in `rules.py`; it imports nothing from the
rules engine. The agent runs it beside `engines.onboarding_rules` on every stage run and stops with
ERROR on any difference, and the Supervisor's SUP-05 re-check uses it, so one implementation
checks the other. Same rules as the engine:
  role not authorised           -> role FAIL, nothing else is checked
  training: no record            -> UNKNOWN (ONB_TRAINING_MISSING)
            not completed / no expiry -> FAIL (ONB_TRAINING_INCOMPLETE)
            expired before as-of   -> FAIL (ONB_TRAINING_EXPIRED)
            (several records for one course: the one that expires last counts)
  policy: current version acknowledged -> PASS; none -> FAIL (ACK_MISSING); other -> FAIL (OLD)
  gate: any FAIL -> NO_GO; else any UNKNOWN -> NEEDS_INPUT; else GO
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from credassure.core.blockers import BlockerCode

from . import rules


@dataclass(frozen=True)
class Check:
    gate: str
    rules: Mapping[str, str]
    blockers: tuple[tuple[str, BlockerCode], ...]


def _latest(trainings: list[Mapping[str, Any]], course: str) -> Mapping[str, Any] | None:
    found: Mapping[str, Any] | None = None
    for record in trainings:
        if record.get("code") != course:
            continue
        expiry = str(record.get("expires_on") or "")
        if found is None or expiry >= str(found.get("expires_on") or ""):
            found = record  # a later (or equal, later in the list) expiry replaces the earlier one
    return found


def _training(record: Mapping[str, Any] | None, as_of: date) -> BlockerCode | None:
    if record is None:
        return BlockerCode.ONB_TRAINING_MISSING
    expiry = record.get("expires_on")
    if record.get("status") != "completed" or not expiry:
        return BlockerCode.ONB_TRAINING_INCOMPLETE
    if as_of > date.fromisoformat(str(expiry)):
        return BlockerCode.ONB_TRAINING_EXPIRED
    return None


def check(profile: Mapping[str, Any], as_of: date) -> Check:
    if profile.get("role") not in rules.AUTHORISED_ROLES:
        return Check("NO_GO", {"role": "FAIL"}, (("role", BlockerCode.ONB_ROLE_NOT_AUTHORISED),))
    outcome: dict[str, str] = {"role": "PASS"}
    blockers: list[tuple[str, BlockerCode]] = []
    trainings = list(profile.get("trainings") or [])
    for course in rules.MANDATORY:
        code = _training(_latest(trainings, course), as_of)
        if code is None:
            outcome[course] = "PASS"
            continue
        outcome[course] = "UNKNOWN" if code is BlockerCode.ONB_TRAINING_MISSING else "FAIL"
        blockers.append((course, code))
    acknowledged = profile.get("policy_ack_version")
    if acknowledged == rules.POLICY_VERSION:
        outcome["policy_ack"] = "PASS"
    else:
        outcome["policy_ack"] = "FAIL"
        old = BlockerCode.ONB_ACK_OLD_VERSION if acknowledged else BlockerCode.ONB_ACK_MISSING
        blockers.append(("policy_ack", old))
    values = set(outcome.values())
    gate = "NO_GO" if "FAIL" in values else "NEEDS_INPUT" if "UNKNOWN" in values else "GO"
    return Check(gate, outcome, tuple(blockers))


def differences(
    mine: Check, gate: str, rule_outcomes: Mapping[str, str], blockers: Any
) -> list[str]:
    """What the two implementations disagree on (rule ids, "gate", "blockers"); empty when equal."""
    names = sorted(set(mine.rules) | set(rule_outcomes))
    out = [r for r in names if mine.rules.get(r) != rule_outcomes.get(r)]
    if mine.gate != gate:
        out.append("gate")
    if set(mine.blockers) != {(str(r), BlockerCode(c)) for r, c in blockers}:
        out.append("blockers")
    return out
