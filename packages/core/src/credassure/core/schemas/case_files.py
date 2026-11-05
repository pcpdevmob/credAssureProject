"""Case-file schemas (DATA_SPEC §2, schema_version 1.0)."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class OrderFile(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    order_ref: str
    customer_name: str
    order_value: Decimal
    currency: Literal["INR"] = "INR"
    po_date: date
    delivery_weeks: list[int]
    payment_terms_days: int
    advance_pct: Decimal
    enterprise_class: Literal["micro", "small", "medium"]
    investment: Decimal
    turnover: Decimal


class CreditLine(BaseModel):
    lender: str
    type: str
    sanctioned: Decimal
    drawn: Decimal


class ConfirmedMitigation(BaseModel):
    type: str
    amount: Decimal
    week: int
    evidence_ref: str


class OpeningPosition(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    as_of_week_start: date
    opening_cash: Decimal
    min_cash_buffer: Decimal
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
