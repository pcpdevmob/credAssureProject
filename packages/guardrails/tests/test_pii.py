"""PII redaction (NFR-07, ONB-06, VER-03): Aadhaar with Verhoeff, PAN, IFSC, account near a keyword,
Indian mobile, email. Identifiers are generated here and never stored (RESOURCES §2)."""

from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from credassure.core.money import format_inr
from credassure.guardrails import pii


def aadhaar(body11: str) -> str:
    """A 12-digit Aadhaar-format number whose last digit is the Verhoeff check digit."""
    return body11 + pii.verhoeff_digit(body11)


GOOD = aadhaar("23456789012")
BAD = GOOD[:-1] + str((int(GOOD[-1]) + 1) % 10)  # same shape, wrong check digit


def test_verhoeff_known_vector() -> None:
    # Classic published example: 236 -> check digit 3.
    assert pii.verhoeff_digit("236") == "3"
    assert pii.verhoeff_valid("2363")
    assert not pii.verhoeff_valid("2364")


@pytest.mark.parametrize(
    "text",
    [
        f"Aadhaar {GOOD}",
        f"my id is {GOOD[:4]} {GOOD[4:8]} {GOOD[8:]}",
    ],
)
def test_valid_aadhaar_is_redacted(text: str) -> None:
    out = pii.redact(text)
    assert "[REDACTED_AADHAAR]" in out
    assert GOOD[-4:] not in out


def test_aadhaar_failing_verhoeff_is_kept() -> None:
    # A 12-digit number that is not a valid Aadhaar is probably an amount or a reference.
    assert pii.redact(f"ref {BAD}") == f"ref {BAD}"


def test_aadhaar_cannot_start_with_0_or_1() -> None:
    lead1 = aadhaar("13456789012")
    assert "AADHAAR" not in pii.redact(lead1)


@pytest.mark.parametrize(
    ("text", "tag"),
    [
        ("PAN ABCPE1234F on file", "[REDACTED_PAN]"),
        ("pan: abcpe1234f", "[REDACTED_PAN]"),
        ("IFSC SBIN0001234", "[REDACTED_IFSC]"),
        ("branch hdfc0abc123", "[REDACTED_IFSC]"),
        ("account no 123456789012345", "[REDACTED_ACCOUNT]"),
        ("A/C: 001234567890", "[REDACTED_ACCOUNT]"),
        ("acct 9876543210", "[REDACTED_ACCOUNT]"),
        ("call 9876543210", "[REDACTED_PHONE]"),
        ("call +91 98765 43210", "[REDACTED_PHONE]"),
        ("call +91-9876543210", "[REDACTED_PHONE]"),
        ("mail priya.k+loans@example.co.in", "[REDACTED_EMAIL]"),
        ("x@y.io", "[REDACTED_EMAIL]"),
    ],
)
def test_identifiers_are_redacted(text: str, tag: str) -> None:
    assert tag in pii.redact(text)


@pytest.mark.parametrize(
    "text",
    [
        "₹1,42,00,000",
        "1.42 crore",
        "142 lakh",
        "Rs. 142L",
        "12%",
        "14200000",
        "peak shortfall in week 9 of 26",
        "case CA-2026-0001",
        "offer OF-01-A v2",
        "12-11-2026",
        "2026-11-15",
        "KFS-OF-02-A-v1-SCH",
        "number 123456789012345 with no account keyword",
        "",
    ],
)
def test_ordinary_text_is_untouched(text: str) -> None:
    assert pii.redact(text) == text


def test_account_keyword_must_be_near() -> None:
    far = "account " + "x" * 40 + " 123456789012"
    assert "ACCOUNT" not in pii.redact(far)


def test_redact_is_idempotent() -> None:
    text = f"PAN ABCPE1234F, Aadhaar {GOOD}, mail a@b.in, call 9876543210"
    once = pii.redact(text)
    assert pii.redact(once) == once


def test_find_reports_kinds_and_spans() -> None:
    text = f"PAN ABCPE1234F and {GOOD}"
    hits = pii.find(text)
    assert {h.kind for h in hits} == {"PAN", "AADHAAR"}
    for h in hits:
        assert text[h.start : h.end] in {"ABCPE1234F", GOOD}


def test_redact_value_walks_nested_data() -> None:
    data = {"note": "PAN ABCPE1234F", "items": ["a@b.in", 5], "n": None}
    out = pii.redact_value(data)
    assert out == {"note": "PAN [REDACTED_PAN]", "items": ["[REDACTED_EMAIL]", 5], "n": None}


def test_dashed_aadhaar_shape_is_not_aadhaar() -> None:
    # Only XXXX XXXX XXXX or 12 contiguous digits count; dashes read as a reference.
    assert "AADHAAR" not in pii.redact(f"{GOOD[:4]}-{GOOD[4:8]}-{GOOD[8:]}")


PHONE_LIKE = "6000000000"  # ₹600 crore in bare rupee digits; PHONE-shaped


@pytest.mark.parametrize(
    "text",
    [
        f"₹{GOOD}",
        f"₹ {GOOD}",
        f"Rs. {GOOD}",
        f"Rs{GOOD}",
        f"INR {GOOD}",
        f"{GOOD}/-",
        f"{GOOD}.50",
        f"1,{GOOD}",
        f"{GOOD},00",
        f"amount ₹{GOOD[:4]} {GOOD[4:8]} {GOOD[8:]}",
        f"₹{PHONE_LIKE}",
        f"Rs. {PHONE_LIKE}/-",
        f"{PHONE_LIKE}.00",
        f"A/C balance ₹{PHONE_LIKE}",
    ],
)
def test_money_is_never_masked(text: str) -> None:
    assert pii.find(text) == []


def test_plain_aadhaar_still_masked_next_to_money() -> None:
    out = pii.redact(f"paid ₹{GOOD}; Aadhaar {GOOD}")
    assert out == f"paid ₹{GOOD}; Aadhaar [REDACTED_AADHAAR]"


def _formats(paise: int, body12: str) -> list[str]:
    rupees = Decimal(paise) / 100
    whole = str(paise // 100)
    lakh = (rupees / 100000).normalize()
    crore = (rupees / 10000000).normalize()
    return [
        format_inr(rupees),
        f"{format_inr(rupees)}/-",
        f"Rs. {whole}",
        f"Rs{whole}",
        f"INR {whole}",
        f"₹{whole}",
        f"{whole}/-",
        f"{whole}.{paise % 100:02d}",
        f"{format_inr(rupees).lstrip('₹')}/-",
        f"{lakh:f} lakh",
        f"{lakh:f} lac",
        f"{lakh:f}L",
        f"{crore:f} crore",
        f"{crore:f} Cr",
        f"{crore:f} Cr.",
        # Verhoeff-valid and phone-shaped bodies on purpose: the money context must win.
        f"₹{body12}",
        f"Rs. {body12}/-",
        f"INR {body12}.00",
        f"₹{body12[:10]}",
    ]


@settings(max_examples=1000, deadline=None)
@given(
    paise=st.integers(min_value=0, max_value=10**14),
    body11=st.from_regex(r"[2-9][0-9]{10}", fullmatch=True),
    pick=st.integers(min_value=0, max_value=18),
)
def test_property_rupee_amounts_are_never_masked(paise: int, body11: str, pick: int) -> None:
    text = _formats(paise, aadhaar(body11))[pick]
    assert pii.find(text) == [], text
