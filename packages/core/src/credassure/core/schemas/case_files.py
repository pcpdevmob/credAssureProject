"""Case-file schemas (DATA_SPEC §2, schema_version 1.0).

Fields the Working Capital validator requires (engines.validators REQUIRED_ORDER/REQUIRED_OPENING)
are optional at upload: a well-formed file with a gap is stored, and the stage answers
NEEDS_INPUT naming the field (WC-01). A malformed value is still refused at upload (UI-02).
"""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class OrderFile(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    order_ref: str | None = None
    customer_name: str
    order_value: Decimal | None = None
    currency: Literal["INR"] = "INR"
    po_date: date | None = None
    delivery_weeks: list[int] | None = None
    payment_terms_days: int | None = None
    advance_pct: Decimal
    enterprise_class: Literal["micro", "small", "medium"] | None = None
    investment: Decimal
    turnover: Decimal
    home_state: str = Field(default="IN-MH", pattern=r"^IN-[A-Z]{2}$")  # ADR 0019 retrieval filter


class CreditLine(BaseModel):
    lender: str
    type: str
    sanctioned: Decimal
    drawn: Decimal


class ConfirmedMitigation(BaseModel):
    type: str
    amount: Decimal
    week: int
    evidence_ref: str = Field(min_length=1)  # WC-05: an offset needs its source


class OpeningPosition(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    as_of_week_start: date | None = None
    opening_cash: Decimal | None = None
    min_cash_buffer: Decimal | None = None
    credit_lines: list[CreditLine] = Field(default_factory=list)
    confirmed_mitigations: list[ConfirmedMitigation] = Field(default_factory=list)


class CostRow(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    week: int
    category: Literal["components", "labour", "testing", "packaging", "logistics", "overheads"]
    amount: Decimal


class ReceiptRow(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    week: int
    source: Literal["order_advance", "order_milestone", "other_customer"]
    amount: Decimal
    confirmed: bool


class ReceivableRow(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    invoice_id: str
    customer: str
    amount: Decimal
    due_week: int
    expected_week: int


class PayableRow(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    bill_id: str
    supplier: str
    amount: Decimal
    bill_week: int | None = None  # needed for the 45-day MSE check (RESOURCES D5)
    due_week: int
    msme_supplier: bool


class InventoryRow(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    week: int
    opening_value: Decimal
    purchases: Decimal
    consumption: Decimal
    closing_value: Decimal
