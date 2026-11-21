"""Employee Onboarding Agent entry point: tools -> rules -> explanation -> audit.

`run_readiness_gate` is what the Supervisor, the API and the test harness all call, so they
always get the same decision for the same inputs.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

from . import rules
from .audit import audit_event, observe
from .checker import evaluate_readiness
from .explain import PROMPT_VERSION, LLMFn, explain
from .schemas import Decision, StageResult
from .tools import get_employee_record, get_policy_acknowledgements, get_training_status


@observe(name="employee_onboarding")
def run_readiness_gate(case_id: str, employee_id: str, as_of: Optional[date] = None,
                       llm: Optional[LLMFn] = None, hr_db: Optional[Path] = None,
                       case_checklist: Optional[dict] = None) -> StageResult:
    """Check the preparer (and, if given, the optional case checklist) for one case."""
    as_of = as_of or date.today()
    try:
        emp = get_employee_record(employee_id, hr_db)
        training = get_training_status(employee_id, hr_db) if emp else []
        acks = get_policy_acknowledgements(employee_id, hr_db) if emp else []
        result = evaluate_readiness(case_id, emp, training, as_of, employee_id=employee_id,
                                    case_checklist=case_checklist, acknowledgements=acks)
    except Exception as exc:   # HR store down or broken -> ERROR, never a guessed GO
        result = StageResult(case_id=case_id, subject_id=employee_id, decision=Decision.ERROR,
                             as_of=as_of, rules_version=rules.RULES_VERSION,
                             warnings=[f"{type(exc).__name__}: {exc}"],
                             next_action="Retry; if it fails again, escalate to the administrator.")
    result = explain(result, llm=llm)
    event_id = audit_event(case_id, actor_role="onboarding_agent", action="readiness_check",
                           status=result.decision.value,
                           details={"employee_id": employee_id, "blockers": result.blockers,
                                    "rules_version": result.rules_version, "as_of": as_of.isoformat(),
                                    "explanation_source": result.explanation_source,
                                    "prompt_version": PROMPT_VERSION, "trace_id": result.trace_id})
    result.output_ref = f"audit_events:{event_id}"
    return result
