"""KFS metadata schema (DATA_SPEC §4, schema_version 1.0). The body stays Markdown."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class KfsFee(BaseModel):
    name: str
    amount: Decimal | None = None
    text: str | None = None


class KfsMetadata(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    doc_id: str
    case_id: str
    offer_id: str | None = None
    loan_amount: Decimal | None = None
    tenure_months: int | None = None
    interest_rate_type: Literal["fixed", "floating"] | None = None
    apr: Decimal | None = None
    fees: list[KfsFee] = Field(default_factory=list)
    contingent_charges: str | None = None
    grievance_contact: str | None = None
