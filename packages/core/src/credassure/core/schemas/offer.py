"""Lender offer schema (DATA_SPEC §3, schema_version 1.0)."""

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class OfferFee(BaseModel):
    name: str
    basis: Literal["fixed", "pct_of_principal"]
    value: Decimal
    timing: Literal["upfront", "monthly", "annual"]
    gst_applicable: bool


class Insurance(BaseModel):
    premium: Decimal
    financed: bool


class Guarantee(BaseModel):
    scheme: Literal["CGTMSE"] = "CGTMSE"
    annual_fee_pct: Decimal
    basis: Literal["y1_guaranteed_then_outstanding", "sanctioned", "outstanding"] = (
        "y1_guaranteed_then_outstanding"
    )
    passed_to_borrower: bool
    gst_applicable: bool


class Repayment(BaseModel):
    frequency: Literal["monthly"] = "monthly"
    method: Literal["emi", "equal_principal"]


class Offer(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    lender_id: str
    lender_name: str
    offer_id: str
    version: int
    product: Literal["wc_term_loan"] = "wc_term_loan"
    principal: Decimal
    rate_type: Literal["fixed", "floating"]
    annual_rate: Decimal
    benchmark: Literal["EBLR", "MCLR"] | None = None
    spread: Decimal | None = None
    tenure_months: int
    moratorium_months: int = 0
    repayment: Repayment
    stated_instalment: Decimal | None = None
    disbursal_date: date
    first_repayment_date: date
    fees: list[OfferFee] = Field(default_factory=list)
    insurance: Insurance | None = None
    guarantee: Guarantee | None = None
    prepayment_terms: str | None = None
    kfs_doc_id: str
    lender_type: Literal["commercial_bank", "nbfc", "sfb", "coop_bank"] | None = None  # ADR 0019
