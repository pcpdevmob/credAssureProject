"""Pydantic schemas for the CredAssure Employee Onboarding Agent (BRD v3.1, section 8.3).

`Employee`, `TrainingRecord` and `PolicyAcknowledgement` live in the separate SQLite HR
store (BR-14: HR data and case data are stored apart). `StageResult` is the structured
result every agent returns to the Supervisor (SUP-04: decision, evidence, blockers,
output reference). It is a draft until the team freezes the shared result format;
keep these field names or map them in one place.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class EmploymentStatus(str, Enum):
    ACTIVE = "active"
    ON_LEAVE = "on_leave"
    EXITED = "exited"


class TrainingStatus(str, Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"


class Employee(BaseModel):
    schema_version: str = SCHEMA_VERSION
    employee_id: str
    full_name: str
    role: Optional[str] = None            # None = missing in the HR record -> NEEDS_INPUT
    department: Optional[str] = None
    manager_id: Optional[str] = None
    employment_status: EmploymentStatus
    authorised_tasks: list[str] = Field(default_factory=list)


class TrainingRecord(BaseModel):
    schema_version: str = SCHEMA_VERSION
    record_id: str
    employee_id: str
    course_code: str
    course_name: str
    status: TrainingStatus
    completed_on: Optional[date] = None
    valid_until: Optional[date] = None    # None = never expires
    evidence_id: Optional[str] = None     # LMS completion ID


class PolicyAcknowledgement(BaseModel):
    schema_version: str = SCHEMA_VERSION
    record_id: str
    employee_id: str
    policy_code: str
    policy_name: str
    acknowledged_on: Optional[date] = None
    valid_until: Optional[date] = None
    evidence_id: Optional[str] = None     # HR portal acknowledgement ID


class Decision(str, Enum):
    GO = "GO"
    NO_GO = "NO_GO"
    NEEDS_INPUT = "NEEDS_INPUT"
    ERROR = "ERROR"


class CheckOutcome(str, Enum):
    """BRD ONB-02: pass, fail or unknown per rule."""
    PASS = "pass"
    FAIL = "fail"          # a known gap -> NO_GO
    UNKNOWN = "unknown"    # record missing or not trustworthy -> NEEDS_INPUT
    UNVERIFIED = "unknown" # older name, kept as an alias


class CheckResult(BaseModel):
    check_id: str                 # e.g. ROLE_AUTHORISED, TRAINING:INFOSEC, ACK:POL_CREDIT
    description: str
    outcome: CheckOutcome
    reason_code: Optional[str] = None   # e.g. EXPIRED, MISSING, NO_EVIDENCE
    detail: str                   # factual sentence written by code
    source: Optional[str] = None  # e.g. hr.training_records:TR-0012


class LedgerFact(BaseModel):
    """A validated fact the AI is allowed to quote (goes to the fact ledger)."""
    key: str
    value: str
    source: str


class StageResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    agent: str = "employee_onboarding"
    stage: str = "readiness"
    case_id: str
    subject_id: str               # the preparer's employee ID
    decision: Decision
    checks: list[CheckResult] = Field(default_factory=list)       # the evidence, one per rule
    blockers: list[str] = Field(default_factory=list)             # check IDs that did not pass
    warnings: list[str] = Field(default_factory=list)
    explanation: str = ""         # plain-language text for the preparer
    explanation_source: str = "template"   # "llm" or "template"
    next_action: str = ""
    facts: list[LedgerFact] = Field(default_factory=list)
    rules_version: str = ""
    as_of: date
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    output_ref: str = ""          # where the result is stored, e.g. audit_events:42
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
