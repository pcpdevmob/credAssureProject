"""PII v2 (ADR 0030, scope #57, #58): GSTIN, UPI ID, card and Udyam recognisers behind the
Phase 6 interface, Presidio with no NER model or the regex fallback, and the money gate."""

import random
from decimal import Decimal

import pytest

from credassure.core.money import format_inr
from credassure.guardrails import pii, recognisers

GSTIN = "27AAPFU0939F1Z" + recognisers.gstin_check_char("27AAPFU0939F1Z")
CARD = "4111 1111 1111 1111"  # Luhn-valid test card number (synthetic)


@pytest.mark.parametrize(
    ("text", "tag"),
    [
        (f"GSTIN {GSTIN} on the invoice", "[REDACTED_GSTIN]"),
        (f"gstin {GSTIN.lower()}", "[REDACTED_GSTIN]"),
        ("Pay to ravi.k@okaxis today", "[REDACTED_UPI]"),
        ("UPI 9876501234@ybl", "[REDACTED_UPI]"),
        (f"card {CARD} expiring", "[REDACTED_CARD]"),
        ("card 4111-1111-1111-1111", "[REDACTED_CARD]"),
        ("Udyam no UDYAM-MH-26-0012345", "[REDACTED_UDYAM]"),
    ],
)
def test_scope57_v2_kinds_are_redacted(text: str, tag: str) -> None:
    assert tag in pii.redact(text)


@pytest.mark.parametrize(
    "text",
    [
        "27AAPFU0939F1ZX is not a GSTIN (bad check character)",
        "4111 1111 1111 1112 fails Luhn",
        "write to team@example (no PSP handle)",
        "ravi@notabank is not a UPI handle",
        "Invoice INV-2026-0012345 and order PO-CA-2026-0001",
    ],
)
def test_scope57_lookalikes_survive(text: str) -> None:
    assert pii.redact(text) == text


def test_scope57_email_still_wins_over_upi_shape() -> None:
    assert pii.redact("mail ravi@okaxis.com") == "mail [REDACTED_EMAIL]"


def test_scope57_engine_is_presidio_when_installed() -> None:
    pytest.importorskip("presidio_analyzer")
    assert recognisers.ENGINE == "presidio"
    engine, found = recognisers.spans(f"{GSTIN} and {CARD}")
    assert engine == "presidio" and [k for k, _, _ in found] == ["GSTIN", "CARD"]


def test_scope57_regex_fallback_finds_the_same_spans(monkeypatch: pytest.MonkeyPatch) -> None:
    text = f"{GSTIN}, ravi.k@okaxis, {CARD}, UDYAM-MH-26-0012345, ₹1,42,00,000"
    _, primary = recognisers.spans(text)
    monkeypatch.setattr(recognisers, "ENGINE", "regex")
    engine, fallback = recognisers.spans(text)
    assert engine == "regex" and sorted(fallback) == sorted(primary) and len(primary) == 4


def test_scope57_presidio_error_falls_back_and_still_scans(monkeypatch: pytest.MonkeyPatch) -> None:
    class Broken:
        def analyze(self, *a: object, **k: object) -> list[object]:
            raise RuntimeError("recogniser failed")

    monkeypatch.setattr(recognisers, "ENGINE", "presidio")
    monkeypatch.setattr(recognisers, "_RECOGNISERS", [(recognisers.KINDS[0], Broken())])
    engine, found = recognisers.spans(f"GSTIN {GSTIN}")
    assert engine == "regex" and found == [("GSTIN", 6, 21)]  # fail closed: still found


# --- money-preservation gate (ADR 0030 §4, scope #58) ----------------------------------------


@pytest.mark.parametrize(
    "paise", [1, 99_99_999_99, 1_42_00_000_00, 1_50_00_000_00, 4_111_111_111_111_111]
)
def test_scope58_rupee_figures_are_never_masked(paise: int) -> None:
    shown = format_inr(Decimal(paise) / 100)
    for text in (f"₹{shown}", f"Rs. {shown}", f"INR {shown}", f"{shown}/-", f"amount {shown}"):
        assert pii.redact(text) == text


def test_scope58_aadhaar_checksum_agreement_on_20000_numbers() -> None:
    rng = random.Random(20261118)  # noqa: S311 - seeded test fixture, not security
    agree = 0
    for _ in range(10_000):
        body = str(rng.randint(2, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(10))
        good = body + pii.verhoeff_digit(body)
        bad = body + str((int(pii.verhoeff_digit(body)) + rng.randint(1, 9)) % 10)
        # agreement on the Aadhaar decision ("91..." numbers are also a +91 mobile: Phase 6)
        agree += "AADHAAR" in {h.kind for h in pii.find(f"id {good}")}
        agree += "AADHAAR" not in {h.kind for h in pii.find(f"id {bad}")}
    assert agree == 20_000
