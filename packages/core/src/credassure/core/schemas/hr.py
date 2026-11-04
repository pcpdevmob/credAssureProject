"""HR profile schema (DATA_SPEC §1, schema_version 1.0). Synthetic fields only."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class TrainingRecord(BaseModel):
    code: str
    name: str
    status: Literal["current", "expired", "in_progress"]
    expires_on: date | None = None


class HrProfile(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    emp_id: str
    display_name: str
    role: Literal[
        "credit_proposal_officer",
        "senior_finance_analyst",
        "finance_analyst",
        "accounts_executive",
    ]
    trainings: list[TrainingRecord] = Field(default_factory=list)
    policy_ack_version: str | None = None
