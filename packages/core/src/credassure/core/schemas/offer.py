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
    issue_date: date | None = None  # offer/KFS issue date, on or before AS_OF_DATE
    disbursal_date: date
    first_repayment_date: date
    fees: list[OfferFee] = Field(default_factory=list)
    insurance: Insurance | None = None
    guarantee: Guarantee | None = None
    prepayment_terms: str | None = None
    kfs_doc_id: str
    lender_type: Literal["commercial_bank", "nbfc", "sfb", "coop_bank"] | None = None  # ADR 0019


OFFER_ID = r"^OF-[A-Za-z0-9-]{1,60}$"  # no "." or spaces: it becomes part of ledger keys
LENDER_ID = r"^[A-Za-z0-9-]{1,40}$"
KFS_DOC_ID = r"^KFS-[A-Za-z0-9-]{1,60}$"


class OfferUpload(Offer):
    """An uploaded offer (LW-01). Material terms may be absent: the audit flags them (LW-02, BR-06)
    instead of the upload rejecting the file. Everything present is still type-checked, and ids
    are constrained because they become ledger keys and narrative text."""

    offer_id: str = Field(pattern=OFFER_ID)
    lender_id: str = Field(pattern=LENDER_ID)
    kfs_doc_id: str = Field(pattern=KFS_DOC_ID)
    version: int = Field(ge=1, le=99)
    # plain words only: it is quoted in the negotiation message (LW-12)
    lender_name: str = Field(pattern=r"^[A-Za-z][A-Za-z .,&()'-]{0,119}$")

    principal: Decimal | None = None  # type: ignore[assignment]
    rate_type: Literal["fixed", "floating"] | None = None  # type: ignore[assignment]
    annual_rate: Decimal | None = None  # type: ignore[assignment]
    tenure_months: int | None = None  # type: ignore[assignment]
    repayment: Repayment | None = None  # type: ignore[assignment]
    disbursal_date: date | None = None  # type: ignore[assignment]
    first_repayment_date: date | None = None  # type: ignore[assignment]
    fees: list[OfferFee] | None = None  # type: ignore[assignment]  # absent != no fees
