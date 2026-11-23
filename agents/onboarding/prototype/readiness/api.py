"""HTTP endpoints of the Employee Onboarding Agent (FastAPI router).

Include it in the team's backend:   app.include_router(readiness.api.router)

  GET  /api/agents/onboarding/readiness?caseId=...   the FinBridge UI's onboardingService call
  POST /api/agents/onboarding/readiness              the same check, with a JSON body (Supervisor, tests)
  POST /api/agents/onboarding/message                a chat message: redact PII, answer readiness questions
  GET  /api/agents/onboarding/rules                  the current rule set, for the UI checklist
  POST /api/cases/{case_id}/readiness                older path, kept so earlier callers keep working

Decisions are "GO", "NO-GO", "NEEDS_INPUT" or "ERROR" (BRD glossary). Every rule is listed with
pass, fail or unknown (ONB-02), and every rule that did not pass says who must fix it.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from . import case_store, rules
from .chat import handle_message
from .gate import run_readiness_gate
from .identity import resolve_preparer
from .schemas import CheckOutcome, CheckResult, Decision, StageResult

router = APIRouter(prefix="/api", tags=["employee onboarding"])

ID = r"^[A-Za-z0-9_-]{1,64}$"
FixBy = Literal["preparer", "manager", "hr", "case"]
API_DECISION = {Decision.GO: "GO", Decision.NO_GO: "NO-GO", Decision.NEEDS_INPUT: "NEEDS_INPUT",
                Decision.ERROR: "ERROR"}


# ---------------------------------------------------------------- request and response shapes
class CaseChecklist(BaseModel):
    """Optional case-intake checklist. If sent, all four answers are required."""
    model_config = ConfigDict(extra="forbid")
    business_identity: StrictBool
    requested_amount: StrictBool
    purchase_order: StrictBool
    cashflow_data: StrictBool


class ReadinessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"case_id": "CASE-001", "preparer_id": "EMP-001", "as_of": "2026-11-02"}]})
    case_id: str = Field(pattern=ID)
    preparer_id: Optional[str] = Field(default=None, pattern=ID)
    user: Optional[str] = Field(default=None, max_length=128)    # UI login, mapped to an employee
    as_of: Optional[date] = None        # leave empty for today; set it for repeatable tests and demos
    checklist: Optional[CaseChecklist] = None


class LegacyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preparer_id: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9-]+$")
    checklist: Optional[CaseChecklist] = None
    as_of: Optional[date] = None


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"case_id": "CASE-002", "preparer_id": "EMP-007", "message": "Why am I blocked? My PAN is ABCDE1234F",
         "as_of": "2026-11-02"}]})
    case_id: str = Field(pattern=ID)
    preparer_id: Optional[str] = Field(default=None, pattern=ID)
    user: Optional[str] = Field(default=None, max_length=128)
    message: str = Field(min_length=1, max_length=2000)
    as_of: Optional[date] = None


class Rule(BaseModel):
    rule_id: str
    label: str
    outcome: Literal["pass", "fail", "unknown"]
    detail: str
    fix_by: Optional[FixBy] = None      # set when the rule did not pass
    source: Optional[str] = None


class ReadinessResponse(BaseModel):
    case_id: str
    preparer_id: str
    decision: Literal["GO", "NO-GO", "NEEDS_INPUT", "ERROR"]
    rules: list[Rule]                   # every rule with its outcome (ONB-02)
    blockers: list[Rule]                # the rules that did not pass
    warnings: list[str]
    explanation: str
    explanation_source: str
    next_action: str
    rules_version: str
    as_of: date
    trace_id: str
    output_ref: str
    case_found: bool
    detail: StageResult                 # full result: checks, sources, ledger facts


class MessageResponse(BaseModel):
    case_id: str
    preparer_id: str
    reply: str
    intent: Literal["readiness", "pii_only", "out_of_scope"]
    pii_redacted: list[str]
    message_redacted: str
    readiness: Optional[ReadinessResponse] = None


# ---------------------------------------------------------------- helpers
def _fix_by(c: CheckResult) -> FixBy:
    if c.check_id.startswith("CASE:"):
        return "case"
    if c.outcome == CheckOutcome.UNKNOWN:
        return "hr"
    if c.check_id.startswith(("TRAINING:", "ACK:")):
        return "preparer"
    return "manager"   # employment status, role, task authorisation


def _rule(c: CheckResult) -> Rule:
    return Rule(rule_id=c.check_id, label=c.description, outcome=c.outcome.value, detail=c.detail,
                fix_by=None if c.outcome == CheckOutcome.PASS else _fix_by(c), source=c.source)


def to_response(result: StageResult, case_found: bool) -> ReadinessResponse:
    all_rules = [_rule(c) for c in result.checks]
    return ReadinessResponse(
        case_id=result.case_id, preparer_id=result.subject_id, decision=API_DECISION[result.decision],
        rules=all_rules, blockers=[r for r in all_rules if r.outcome != "pass"], warnings=result.warnings,
        explanation=result.explanation, explanation_source=result.explanation_source,
        next_action=result.next_action, rules_version=result.rules_version, as_of=result.as_of,
        trace_id=result.trace_id, output_ref=result.output_ref, case_found=case_found, detail=result)


def _who(case_id: str, preparer_id: Optional[str], user: Optional[str]) -> tuple[Optional[dict], str]:
    case = case_store.get_case(case_id)
    emp, _how = resolve_preparer(preparer_id, user, case)
    if emp is None:
        if case is None:
            raise HTTPException(404, f"Case '{case_id}' not found, and no preparer was given.")
        raise HTTPException(422, f"No preparer is recorded for case '{case_id}'. Send preparerId or user.")
    return case, emp


def _check(case_id: str, preparer_id: Optional[str], user: Optional[str], as_of: Optional[date],
           checklist: Optional[CaseChecklist]) -> ReadinessResponse:
    case, emp = _who(case_id, preparer_id, user)
    result = run_readiness_gate(case_id, emp, as_of=as_of,
                                case_checklist=checklist.model_dump() if checklist else None)
    if case is not None and result.decision != Decision.ERROR:
        case_store.set_readiness_status(case_id, API_DECISION[result.decision])
    return to_response(result, case_found=case is not None)


# ---------------------------------------------------------------- endpoints
@router.get("/agents/onboarding/readiness", response_model=ReadinessResponse,
            summary="Readiness of the case's preparer (used by the FinBridge UI)")
def get_readiness(caseId: str = Query(pattern=ID),
                  preparerId: Optional[str] = Query(default=None, pattern=ID),
                  user: Optional[str] = Query(default=None, max_length=128),
                  asOf: Optional[date] = None) -> ReadinessResponse:
    return _check(caseId, preparerId, user, asOf, None)


@router.post("/agents/onboarding/readiness", response_model=ReadinessResponse,
             summary="Readiness check with a JSON body (Supervisor, test harness)")
def post_readiness(body: ReadinessRequest) -> ReadinessResponse:
    return _check(body.case_id, body.preparer_id, body.user, body.as_of, body.checklist)


@router.post("/agents/onboarding/message", response_model=MessageResponse,
             summary="A chat message for the Onboarding Agent: PII redacted, readiness explained")
def post_message(body: MessageRequest) -> MessageResponse:
    case, emp = _who(body.case_id, body.preparer_id, body.user)
    out = handle_message(body.case_id, emp, body.message, as_of=body.as_of)
    res = out.pop("readiness")
    if res is not None and case is not None and res.decision != Decision.ERROR:
        case_store.set_readiness_status(body.case_id, API_DECISION[res.decision])
    return MessageResponse(**{**out, "preparer_id": emp},
                           readiness=to_response(res, case is not None) if res is not None else None)


@router.get("/agents/onboarding/rules", summary="The qualification rules in force")
def get_rules() -> dict:
    return {
        "rules_version": rules.RULES_VERSION,
        "authorised_roles": sorted(rules.AUTHORISED_ROLES),
        "task": rules.TASK,
        "trainings": [{"code": c, "name": n, "valid_months": m} for c, (n, m) in rules.REQUIRED_TRAININGS.items()],
        "acknowledgements": [{"code": c, "name": n, "valid_months": m}
                             for c, (n, m) in rules.REQUIRED_ACKNOWLEDGEMENTS.items()],
    }


@router.post("/cases/{case_id}/readiness", response_model=ReadinessResponse,
             summary="Older path for the same check (kept for earlier callers)")
def legacy_readiness(case_id: str, body: LegacyRequest) -> ReadinessResponse:
    if case_store.get_case(case_id) is None:
        raise HTTPException(404, f"Case '{case_id}' not found.")
    return _check(case_id, body.preparer_id, None, body.as_of, body.checklist)


@router.get("/readiness/checklist", summary="The optional case-intake checklist items")
def checklist_items() -> list[dict]:
    return [{"key": code.lower(), "label": label} for code, label in rules.CASE_CHECKLIST.items()]
