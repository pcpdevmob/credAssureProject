"""Versioned input schemas (DATA_SPEC sections 1 to 4, schema_version 1.0)."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from credassure.core.schemas import HrProfile, KfsMetadata, Offer, OpeningPosition, OrderFile


def test_order_file_round_trip() -> None:
    order = OrderFile(
        order_ref="PO-1",
        customer_name="Fictional Buyer",
        order_value=Decimal("14200000"),
        po_date=date(2026, 11, 1),
        delivery_weeks=[4, 8],
        payment_terms_days=45,
        advance_pct=Decimal("0.10"),
        enterprise_class="small",
        investment=Decimal("10000000"),
        turnover=Decimal("50000000"),
    )
    assert order.schema_version == "1.0"
    assert order.currency == "INR"
    again = OrderFile.model_validate_json(order.model_dump_json())
    assert again.order_value == Decimal("14200000")


def test_opening_position_names_the_buffer_field() -> None:
    position = OpeningPosition(
        as_of_week_start=date(2026, 11, 15),
        opening_cash=Decimal("500000"),
        min_cash_buffer=Decimal("1000000"),
        credit_lines=[
            {"lender": "Fictional Bank", "type": "OD", "sanctioned": "3000000", "drawn": "0"}
        ],
        confirmed_mitigations=[],
    )
    assert position.schema_version == "1.0"
    assert position.min_cash_buffer == Decimal("1000000")


def test_offer_matches_the_data_spec_shape() -> None:
    offer = Offer(
        lender_id="L-1",
        lender_name="Fictional Bank",
        offer_id="OFF-1",
        version=1,
        principal=Decimal("14200000"),
        rate_type="floating",
        annual_rate=Decimal("0.115"),
        benchmark="EBLR",
        spread=Decimal("0.03"),
        tenure_months=36,
        moratorium_months=0,
        repayment={"frequency": "monthly", "method": "emi"},
        stated_instalment=Decimal("470000"),
        disbursal_date=date(2026, 11, 20),
        first_repayment_date=date(2026, 12, 20),
        fees=[
            {
                "name": "processing",
                "basis": "pct_of_principal",
                "value": "0.01",
                "timing": "upfront",
                "gst_applicable": True,
            }
        ],
        insurance=None,
        guarantee=None,
        prepayment_terms="nil after 6 months",
        kfs_doc_id="KFS-1",
    )
    assert offer.schema_version == "1.0"
    assert offer.product == "wc_term_loan"
    assert offer.repayment.method == "emi"


def test_offer_rejects_a_non_inr_product_name() -> None:
    with pytest.raises(ValidationError):
        Offer(
            lender_id="L-1",
            lender_name="Fictional Bank",
            offer_id="OFF-1",
            version=1,
            product="term_loan",  # type: ignore[arg-type]
            principal=Decimal("1"),
            rate_type="fixed",
            annual_rate=Decimal("0.12"),
            tenure_months=12,
            repayment={"frequency": "monthly", "method": "emi"},
            disbursal_date=date(2026, 11, 20),
            first_repayment_date=date(2026, 12, 20),
            fees=[],
            kfs_doc_id="KFS-1",
        )


def test_hr_profile_uses_the_synthetic_roles() -> None:
    profile = HrProfile(
        emp_id="E-1",
        display_name="Fictional Preparer",
        role="credit_proposal_officer",
        trainings=[
            {
                "code": "FIN-101",
                "name": "FIN-101 Credit Policy",
                "status": "current",
                "expires_on": "2027-11-15",
            }
        ],
        policy_ack_version="WC-POL v3",
    )
    assert profile.schema_version == "1.0"
    assert profile.trainings[0].status == "current"


def test_hr_profile_rejects_an_unknown_role() -> None:
    with pytest.raises(ValidationError):
        HrProfile(
            emp_id="E-1",
            display_name="Fictional Preparer",
            role="director",  # type: ignore[arg-type]
            trainings=[],
        )


def test_kfs_metadata_round_trip() -> None:
    doc = KfsMetadata(
        doc_id="KFS-1",
        case_id="CA-2026-0001",
        offer_id="OFF-1",
        loan_amount=Decimal("14200000"),
        tenure_months=36,
        interest_rate_type="floating",
        apr=Decimal("0.1707"),
        fees=[{"name": "processing", "amount": "142000"}],
        contingent_charges="penal 2% per month",
        grievance_contact="fictional-grievance@example.com",
    )
    assert doc.schema_version == "1.0"
    assert KfsMetadata.model_validate_json(doc.model_dump_json()).loan_amount == Decimal("14200000")
