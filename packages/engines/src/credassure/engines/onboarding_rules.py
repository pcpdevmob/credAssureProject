"""Preparer readiness rules (ONB-02/03, BR-03/04). Pure; the as-of date is an input, never today.

Rules: the role is authorised; each mandatory training has a completed record that has not
expired; the current policy version is acknowledged. A missing training record is UNKNOWN.
Gate: any FAIL -> NO_GO; else any UNKNOWN -> NEEDS_INPUT; else GO.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from credassure.core.blockers import BlockerCode

Outcome = Literal["PASS", "FAIL", "UNKNOWN"]
AUTHORISED_ROLES = frozenset({"credit_proposal_officer", "senior_finance_analyst"})
MANDATORY = ("AML-201", "DPDP-101", "FIN-101")
POLICY_VERSION = "v3"


@dataclass(frozen=True)
class Readiness:
    gate: Literal["GO", "NO_GO", "NEEDS_INPUT"]
    rules: Mapping[str, Outcome]
    blockers: tuple[tuple[str, BlockerCode], ...]

    @property
    def failed(self) -> list[str]:
        return sorted(k for k, v in self.rules.items() if v != "PASS")


def evaluate(
    profile: Mapping[str, Any],
    as_of: date,
    mandatory: Sequence[str] = MANDATORY,
    policy_version: str = POLICY_VERSION,
) -> Readiness:
    rules: dict[str, Outcome] = {}
    blockers: list[tuple[str, BlockerCode]] = []
    if profile["role"] not in AUTHORISED_ROLES:
        rules["role"] = "FAIL"
        blockers.append(("role", BlockerCode.ONB_ROLE_NOT_AUTHORISED))
    else:
        rules["role"] = "PASS"
        records: dict[str, Mapping[str, Any]] = {}
        for t in sorted(profile.get("trainings", []), key=lambda t: str(t.get("expires_on") or "")):
            records[t["code"]] = t  # the latest expiry wins
        for code in mandatory:
            record = records.get(code)
            if record is None:
                rules[code] = "UNKNOWN"
                blockers.append((code, BlockerCode.ONB_TRAINING_MISSING))
            elif record.get("status") != "completed" or not record.get("expires_on"):
                rules[code] = "FAIL"
                blockers.append((code, BlockerCode.ONB_TRAINING_INCOMPLETE))
            elif date.fromisoformat(str(record["expires_on"])) < as_of:
                rules[code] = "FAIL"
                blockers.append((code, BlockerCode.ONB_TRAINING_EXPIRED))
            else:
                rules[code] = "PASS"
        ack = profile.get("policy_ack_version")
        if ack == policy_version:
            rules["policy_ack"] = "PASS"
        else:
            rules["policy_ack"] = "FAIL"
            code_ = BlockerCode.ONB_ACK_MISSING if not ack else BlockerCode.ONB_ACK_OLD_VERSION
            blockers.append(("policy_ack", code_))
    if "FAIL" in rules.values():
        gate: Literal["GO", "NO_GO", "NEEDS_INPUT"] = "NO_GO"
    elif "UNKNOWN" in rules.values():
        gate = "NEEDS_INPUT"
    else:
        gate = "GO"
    return Readiness(gate, rules, tuple(blockers))
