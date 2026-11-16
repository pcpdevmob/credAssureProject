"""Verification Critic checks (VER-01..05, scope #21): numbers, reasons, banned content, PII,
citations and report sections. Pure: facts, slots and a citation resolver are passed in."""

from collections.abc import Mapping, Sequence

import pytest

from credassure.agents.critic.verify import Fact, report_completeness, verify
from credassure.core.blockers import BlockerCode
from credassure.core.enums import Stage

FACTS = {
    "wc.peak_shortfall": Fact("16200000", "INR"),
    "wc.peak_week": Fact("9", "week"),
    "wc.recommended_amount": Fact("14200000", "INR"),
    "lw.OF-01-B.v1.apr": Fact("0.130012", "rate"),
    "lw.OF-01-B.v1.total_cost": Fact("2585358.91", "INR"),
}
WC_SLOTS = {
    "wc.peak_shortfall": "₹1,62,00,000",
    "wc.peak_week": "9",
    "wc.recommended_amount": "₹1,42,00,000",
    "cmp.recommended_vs_request": "lower than",
}
LW_SLOTS = {
    "rank1.offer": "OF-01-B",
    "rank1.apr": "13.00%",
    "rank1.total_cost": "₹25,85,358.91",
    "excluded.OF-01-C": "OF-01-C is not ranked because its repayments would push cash below the "
    "minimum buffer in week 12",
}


def codes(found: Sequence[object]) -> list[str]:
    return [f.code.value for f in found]  # type: ignore[attr-defined]


# ---- VER-01 numbers -----------------------------------------------------------------------------
def test_VER01_template_figures_that_equal_ledger_facts_pass() -> None:
    text = (
        "Cumulative cash falls to its lowest point in week 9, a peak shortfall of ₹1,62,00,000. "
        "OF-01-B ranks first with an APR of 13.00% and a total cost of ₹25,85,358.91."
    )
    assert verify(text, facts=FACTS) == []


@pytest.mark.parametrize(
    "text",
    [
        "The peak shortfall is ₹1,63,00,000.",  # amount off by a lakh
        "OF-01-B has an APR of 13.02%.",  # rate off by 0.02 pp
        "The shortfall peaks in week 11.",  # bare number not a fact
        "Funds arrive on 12-11-2026.",  # date not in the ledger
        "The need is 1.42 Cr.",  # E4 adversarial formats, none in this ledger
        "The need is ₹ 142 L.",
        "The rate is 12 per cent.",
        "The rate is 0.12.",
        "Funds arrive on 31-02-2026.",  # unparsed: an invalid date
        "The total is ₹1,42,0.",  # unparsed: a truncated amount
    ],
)
def test_VER01_unmatched_figures_are_critical(text: str) -> None:
    found = verify(text, facts={k: v for k, v in FACTS.items() if k != "wc.recommended_amount"})
    assert "VER_UNMATCHED_NUMBER" in codes(found)
    assert all(f.severity.value == "critical" for f in found)


def test_VER01_money_within_one_rupee_and_rate_within_half_a_basis_point_match() -> None:
    assert verify("The total cost is ₹25,85,359.", facts=FACTS) == []
    assert verify("The APR is 13%.", facts=FACTS) == []


def test_VER01_a_slot_that_disagrees_with_the_current_ledger_is_stale() -> None:
    stale = WC_SLOTS | {"wc.peak_shortfall": "₹1,70,00,000"}
    text = "The peak shortfall is ₹1,70,00,000 in week 9."
    found = verify(text, facts=FACTS, slots=stale, stage=Stage.WORKING_CAPITAL)
    assert codes(found) == ["VER_UNMATCHED_NUMBER"]
    assert found[0].target_stage is Stage.WORKING_CAPITAL


# ---- reason containment (model text) -------------------------------------------------------------
def test_VER01_model_sentences_built_from_slots_pass() -> None:
    text = (
        "OF-01-B ranks first, with a true annual cost of 13.00% and a total cost of "
        "₹25,85,358.91. OF-01-C is not ranked because its repayments would push cash below the "
        "minimum buffer in week 12."
    )
    facts = FACTS | {"lw.OF-01-C.v1.breach_week": Fact("12", "week")}
    assert verify(text, facts=facts, slots=LW_SLOTS, model=True) == []


@pytest.mark.parametrize(
    "sentence",
    [
        "OF-01-B ranks first because it has more flexible repayment terms.",  # CA-2026-0005 kind
        "OF-01-B ranks first thanks to its strong reputation.",
        "OF-01-B is the most attractive option for the business.",
        "This lender is known for quick service.",  # no slot at all
    ],
)
def test_VER01_invented_reasons_in_model_text_are_critical(sentence: str) -> None:
    found = verify(sentence, facts=FACTS, slots=LW_SLOTS, model=True, stage=Stage.LENDWISE)
    assert codes(found) == ["VER_UNSUPPORTED_REASON"]
    assert found[0].target_stage is Stage.LENDWISE


def test_VER01_recommended_is_the_domain_term_not_a_judgement() -> None:
    text = "The recommended facility is ₹1,42,00,000."
    assert verify(text, facts=FACTS, slots=WC_SLOTS, model=True) == []


def test_VER01_model_figure_outside_a_slot_fails_even_if_it_equals_another_fact() -> None:
    """Money audit: "recommended ₹1,62,00,000" equals the peak shortfall fact, not the amount."""
    text = "The recommended facility is ₹1,62,00,000."
    assert verify(text, facts=FACTS) == []  # code text: equals a fact
    found = verify(text, facts=FACTS, slots={"wc.peak_week": "9"}, model=True)
    assert "VER_UNMATCHED_NUMBER" in codes(found)


def test_VER01_a_slot_value_with_its_own_semicolon_is_one_sentence() -> None:
    """ONB next actions are code text such as "finish the course; HR records the completion"."""
    slots = {
        "rule.FIN-101": "Credit Policy training (FIN-101)",
        "next.FIN-101": "finish the course; HR records the completion",
    }
    text = (
        "Your Credit Policy training (FIN-101) needs action; finish the course; HR records the"
        " completion."
    )
    assert verify(text, facts={}, slots=slots, model=True) == []
    assert verify(text + " It is risky.", facts={}, slots=slots, model=True) != []


def test_VER01_templates_are_not_held_to_sentence_containment() -> None:
    text = "Fewer than two offers are both comparable and affordable."
    assert verify(text, facts=FACTS, slots=LW_SLOTS, model=False) == []


# ---- VER-03 banned content and PII ---------------------------------------------------------------
@pytest.mark.parametrize(
    "text",
    [
        "We will accept this offer.",
        "Please sign the sanction letter.",
        "The proposal is likely to be approved.",
        "Your loan is pre-approved.",
        "Act now: this offer expires soon.",
        "Market interest rates are rising.",
        "Decision: GO.",
        "We recommend you take OF-01-B.",
    ],
)
def test_VER03_banned_content_is_critical(text: str) -> None:
    assert "VER_BANNED_CONTENT" in codes(verify(text, facts=FACTS))


def test_VER03_working_capital_model_text_never_talks_about_lenders() -> None:
    text = "The bank will lend ₹1,42,00,000."
    found = verify(text, facts=FACTS, slots=WC_SLOTS, model=True, stage=Stage.WORKING_CAPITAL)
    assert "VER_BANNED_CONTENT" in codes(found)


def test_VER03_a_pan_is_critical_and_not_echoed() -> None:
    found = verify("Preparer PAN ABCPE1234F is on file.", facts=FACTS)
    assert "VER_PII" in codes(found)
    assert all("ABCPE1234F" not in f.message and "ABCPE1234F" not in (f.span or "") for f in found)


def test_VER03_code_templates_pass() -> None:
    """The onboarding, WC and negotiation templates are code; the banned list must allow them."""
    texts = [
        "Preparer readiness is blocked:\n- AML/KYC training (AML-201) [AML-201]: This mandatory "
        "training has expired. Next: Retake the course and ask HR to update your training record.",
        "- working-capital policy acknowledgement (WC-POL v3) [policy_ack]: You have not "
        "acknowledged the working-capital policy. Next: Read and acknowledge WC-POL v3 in the HR "
        "portal.",
        "We request that you waive or reduce the processing fee on offer OF-01-A. This is a "
        "request for a revised offer only; the business will choose its lender separately.",
        "Order receipts do not add up to the order value.",
    ]
    for text in texts:
        assert verify(text, facts=FACTS) == [], text


# ---- VER-02 citations ----------------------------------------------------------------------------
PASSAGES: dict[str, tuple[str, str]] = {
    "R-RATE-02-REPO": ("ok", "The policy repo rate is kept at 5.50 per cent."),
    "R-MSME-03": ("superseded", "Small: investment up to ₹10 crore."),
    "R-STATE-001": ("filtered", "Gujarat offers a 5% interest subsidy."),
}


def resolve(ids: Sequence[str]) -> Mapping[str, tuple[str, str]]:
    return {i: PASSAGES.get(i, ("missing", "")) for i in ids}


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Processing fees attract GST [R-GST-99].", "VER_BAD_CITATION"),
        ("A small enterprise has investment up to ₹10 crore [R-MSME-03].", "VER_SUPERSEDED_SOURCE"),
        ("Our state offers a 5% interest subsidy [R-STATE-001].", "VER_BAD_CITATION"),
        ("The repo rate is 6.25% [R-RATE-02-REPO].", "VER_BAD_CITATION"),
    ],
)
def test_VER02_bad_citations_are_critical(text: str, code: str) -> None:
    assert code in codes(verify(text, facts={}, resolve=resolve))


def test_VER02_a_supported_citation_passes_and_its_figure_need_not_be_a_fact() -> None:
    assert verify("The repo rate is 5.50% [R-RATE-02-REPO].", facts={}, resolve=resolve) == []


def test_VER02_citations_without_a_library_fail_closed() -> None:
    assert codes(verify("See [R-RBI-02].", facts={})) == ["VER_BAD_CITATION"]


def test_VER02_rule_ids_in_brackets_are_not_citations() -> None:
    assert verify("Credit Policy training (FIN-101) [FIN-101]: expired.", facts={}) == []


# ---- VER-04 report sections ----------------------------------------------------------------------
def test_VER04_missing_report_section_is_critical() -> None:
    sections = ("Funding need", "Offer comparison", "Approval notice")
    report = "# Proposal\n## Funding need\ntext\n## Offer comparison\ntext\n"
    found = report_completeness(report, sections)
    assert codes(found) == ["VER_REPORT_INCOMPLETE"] and "Approval notice" in found[0].message
    assert report_completeness(report + "## Approval notice\nInternal only.\n", sections) == []


def test_VER04_shipped_section_list_names_the_approval_notice() -> None:
    from credassure.reports.sections import required_sections

    assert "Approval is internal, not loan acceptance" in required_sections()


def test_blocker_code_exists() -> None:
    assert BlockerCode("VER_UNSUPPORTED_REASON")
