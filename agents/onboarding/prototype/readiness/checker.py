"""The qualification rules, decided in code (BRD ONB-02, ONB-03, BR-04, BR-05). No model here.

Each rule gives pass, fail or unknown. Then:
  * any rule fails      -> NO_GO        (a known gap: someone must act)
  * else any is unknown -> NEEDS_INPUT  (a record is missing or cannot be trusted)
  * else                -> GO
Training or an acknowledgement counts only if the HR record shows it, with evidence.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from . import rules
from .schemas import (CheckOutcome, CheckResult, Decision, Employee, LedgerFact,
                      PolicyAcknowledgement, StageResult, TrainingRecord, TrainingStatus)

EXPIRY_WARNING_DAYS = 30


def _check_training(code: str, name: str, recs: list[TrainingRecord], as_of: date) -> CheckResult:
    cid, desc = f"TRAINING:{code}", f"{name} completed, evidenced and in date"
    if not recs:
        return CheckResult(check_id=cid, description=desc, outcome=CheckOutcome.FAIL,
                           reason_code="MISSING", detail=f"No record of '{name}' in the HR system.")
    results = [_check_one(cid, desc, name, r, as_of) for r in recs]
    for wanted in (CheckOutcome.PASS, CheckOutcome.UNKNOWN, CheckOutcome.FAIL):
        for res in results:
            if res.outcome == wanted:
                return res
    return results[0]


def _check_one(cid: str, desc: str, name: str, r: TrainingRecord, as_of: date) -> CheckResult:
    src = f"hr.training_records:{r.record_id}"
    mk = lambda outcome, code, detail: CheckResult(check_id=cid, description=desc, outcome=outcome,
                                                   reason_code=code, detail=detail, source=src)
    if r.status != TrainingStatus.COMPLETED:
        return mk(CheckOutcome.FAIL, "NOT_COMPLETED",
                  f"'{name}' is {r.status.value.replace('_', ' ')}, not completed.")
    if r.completed_on is None or r.completed_on > as_of:
        return mk(CheckOutcome.UNKNOWN, "BAD_DATE",
                  f"'{name}' has a missing or future completion date; HR must correct the record.")
    if r.valid_until is not None and r.valid_until < as_of:
        return mk(CheckOutcome.FAIL, "EXPIRED",
                  f"'{name}' expired on {r.valid_until.isoformat()}.")
    if not r.evidence_id:
        return mk(CheckOutcome.UNKNOWN, "NO_EVIDENCE",
                  f"'{name}' is marked completed but has no completion evidence.")
    until = f", valid until {r.valid_until.isoformat()}" if r.valid_until else ""
    return mk(CheckOutcome.PASS, None, f"'{name}' completed on {r.completed_on.isoformat()}{until} "
              f"(evidence {r.evidence_id}).")


def _check_ack(code: str, name: str, recs: list[PolicyAcknowledgement], as_of: date) -> CheckResult:
    cid, desc = f"ACK:{code}", f"{name} acknowledged and in date"
    mk = lambda outcome, rc, detail, src=None: CheckResult(check_id=cid, description=desc, outcome=outcome,
                                                          reason_code=rc, detail=detail, source=src)
    if not recs:
        return mk(CheckOutcome.FAIL, "ACK_MISSING", f"'{name}' has not been acknowledged.")
    r = max(recs, key=lambda a: (a.valid_until or date.min, a.record_id))   # latest acknowledgement
    src = f"hr.policy_acknowledgements:{r.record_id}"
    if r.acknowledged_on is None or r.acknowledged_on > as_of:
        return mk(CheckOutcome.UNKNOWN, "BAD_DATE",
                  f"'{name}' has a missing or future acknowledgement date; HR must correct the record.", src)
    if r.valid_until is not None and r.valid_until < as_of:
        return mk(CheckOutcome.FAIL, "EXPIRED", f"'{name}' acknowledgement expired on {r.valid_until.isoformat()}.", src)
    if not r.evidence_id:
        return mk(CheckOutcome.UNKNOWN, "NO_EVIDENCE",
                  f"'{name}' is marked acknowledged but has no evidence in the HR portal.", src)
    until = f", valid until {r.valid_until.isoformat()}" if r.valid_until else ""
    return mk(CheckOutcome.PASS, None, f"'{name}' acknowledged on {r.acknowledged_on.isoformat()}{until} "
              f"(evidence {r.evidence_id}).", src)


def _employee_checks(emp: Employee) -> list[CheckResult]:
    src = f"hr.employees:{emp.employee_id}"
    out = []
    active = emp.employment_status.value == "active"
    out.append(CheckResult(
        check_id="EMPLOYMENT_ACTIVE", description="Employee is currently active",
        outcome=CheckOutcome.PASS if active else CheckOutcome.FAIL,
        reason_code=None if active else "NOT_ACTIVE",
        detail=f"Employment status is '{emp.employment_status.value.replace('_', ' ')}'.", source=src))
    if emp.role is None:
        out.append(CheckResult(check_id="ROLE_AUTHORISED", description="Role may prepare proposals",
                               outcome=CheckOutcome.UNKNOWN, reason_code="ROLE_MISSING",
                               detail="No role is recorded in the HR system.", source=src))
    else:
        ok = emp.role in rules.AUTHORISED_ROLES
        out.append(CheckResult(check_id="ROLE_AUTHORISED", description="Role may prepare proposals",
                               outcome=CheckOutcome.PASS if ok else CheckOutcome.FAIL,
                               reason_code=None if ok else "ROLE_NOT_AUTHORISED",
                               detail=f"Role is '{emp.role}'" + ("." if ok else
                                      ", which is not authorised to prepare loan proposals."),
                               source=src))
    ok = rules.TASK in emp.authorised_tasks
    out.append(CheckResult(check_id="TASK_AUTHORISED", description="Manager has authorised this task",
                           outcome=CheckOutcome.PASS if ok else CheckOutcome.FAIL,
                           reason_code=None if ok else "TASK_NOT_AUTHORISED",
                           detail="Task authorisation for proposal preparation is "
                                  + ("on record." if ok else "not on record."), source=src))
    return out


def _case_checks(checklist: dict) -> list[CheckResult]:
    """Case-intake checklist (execution guide, Day 5). Anything not confirmed True blocks."""
    out = []
    for code, label in rules.CASE_CHECKLIST.items():
        ok = checklist.get(code.lower()) is True
        out.append(CheckResult(
            check_id=f"CASE:{code}", description=label,
            outcome=CheckOutcome.PASS if ok else CheckOutcome.FAIL,
            reason_code=None if ok else "CASE_ITEM_MISSING",
            detail=f"'{label}' is " + ("confirmed for this case." if ok else "not confirmed for this case."),
            source="case_checklist"))
    return out


def _next_action(decision: Decision, checks: list[CheckResult]) -> str:
    if decision == Decision.GO:
        return "Proceed to the funding assessment."
    bad = [c for c in checks if c.outcome != CheckOutcome.PASS]
    steps = []
    if any(c.reason_code in {"NOT_ACTIVE", "ROLE_NOT_AUTHORISED", "TASK_NOT_AUTHORISED"} for c in bad):
        steps.append("Reassign the case to an authorised preparer, or obtain authorisation.")
    if any(c.check_id.startswith("TRAINING:") and c.outcome == CheckOutcome.FAIL for c in bad):
        steps.append("Complete or renew the listed training.")
    if any(c.check_id.startswith("ACK:") and c.outcome == CheckOutcome.FAIL for c in bad):
        steps.append("Read and acknowledge the listed policies in the HR portal.")
    if any(c.check_id == "EMPLOYEE_FOUND" for c in bad):
        steps.append("Confirm the preparer's employee ID.")
    elif any(c.outcome == CheckOutcome.UNKNOWN for c in bad):
        steps.append("Ask HR to correct or evidence the flagged records.")
    if any(c.check_id.startswith("CASE:") for c in bad):
        steps.append("Add the missing case items.")
    return " ".join(steps + ["Then re-run the readiness check."])


def evaluate_readiness(case_id: str, employee: Optional[Employee], training: list[TrainingRecord],
                       as_of: date, employee_id: Optional[str] = None,
                       case_checklist: Optional[dict] = None,
                       acknowledgements: Optional[list[PolicyAcknowledgement]] = None) -> StageResult:
    """Pure function: the same inputs always give the same decision, checks and blockers.

    `acknowledgements` are the employee's policy acknowledgements (none given = none on record).
    `case_checklist` (keys: business_identity, requested_amount, purchase_order, cashflow_data)
    adds the optional case-intake checks; None checks the preparer only, as BRD v3.1 asks.
    """
    acknowledgements = acknowledgements or []
    subject = employee.employee_id if employee else (employee_id or "UNKNOWN")
    case_checks = _case_checks(case_checklist) if case_checklist is not None else []

    if employee is None:
        checks = [CheckResult(check_id="EMPLOYEE_FOUND", description="Preparer exists in HR system",
                              outcome=CheckOutcome.UNKNOWN, reason_code="NOT_FOUND",
                              detail=f"Employee ID '{subject}' was not found in the HR system.")]
        training, acknowledgements = [], []
    else:
        checks = _employee_checks(employee)
        by_code: dict[str, list[TrainingRecord]] = {}
        for r in training:
            by_code.setdefault(r.course_code, []).append(r)
        for code, (name, _months) in rules.REQUIRED_TRAININGS.items():
            checks.append(_check_training(code, name, by_code.get(code, []), as_of))
        acks_by: dict[str, list[PolicyAcknowledgement]] = {}
        for a in acknowledgements:
            acks_by.setdefault(a.policy_code, []).append(a)
        for code, (name, _months) in rules.REQUIRED_ACKNOWLEDGEMENTS.items():
            checks.append(_check_ack(code, name, acks_by.get(code, []), as_of))
    checks += case_checks

    outcomes = {c.outcome for c in checks}
    decision = (Decision.NO_GO if CheckOutcome.FAIL in outcomes else
                Decision.NEEDS_INPUT if CheckOutcome.UNKNOWN in outcomes else Decision.GO)
    blockers = [c.check_id for c in checks if c.outcome != CheckOutcome.PASS]

    warnings = []
    soon = as_of + timedelta(days=EXPIRY_WARNING_DAYS)
    for r in training:
        if (r.course_code in rules.REQUIRED_TRAININGS and r.valid_until
                and as_of <= r.valid_until <= soon):
            warnings.append(f"'{r.course_name}' expires on {r.valid_until.isoformat()}; renew soon.")
    for a in acknowledgements:
        if a.policy_code in rules.REQUIRED_ACKNOWLEDGEMENTS and a.valid_until and as_of <= a.valid_until <= soon:
            warnings.append(f"'{a.policy_name}' acknowledgement expires on {a.valid_until.isoformat()}; renew soon.")

    facts = [LedgerFact(key="readiness.decision", value=decision.value, source="employee_onboarding"),
             LedgerFact(key="readiness.rules_version", value=rules.RULES_VERSION, source="employee_onboarding"),
             LedgerFact(key="readiness.as_of", value=as_of.isoformat(), source="employee_onboarding")]
    facts += [LedgerFact(key=f"readiness.check.{c.check_id}", value=c.outcome.value,
                         source=c.source or "employee_onboarding") for c in checks]

    return StageResult(case_id=case_id, subject_id=subject, decision=decision, checks=checks,
                       blockers=blockers, warnings=warnings, next_action=_next_action(decision, checks),
                       facts=facts, rules_version=rules.RULES_VERSION, as_of=as_of)
