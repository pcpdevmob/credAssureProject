"""H13 (ADR 0030 §2): hr.db employee names are masked exactly, any case, whole words only."""

from collections.abc import Iterator

import pytest

from credassure.guardrails import pii


@pytest.fixture(autouse=True)
def names() -> Iterator[None]:
    pii.set_known_names(["Asha Synthetic-01", "Ravi Synthetic-02", "Al", "  "])
    yield
    pii.set_known_names([])


def test_H13_full_employee_name_is_masked_in_any_case() -> None:
    out = pii.redact("Ask asha synthetic-01 about Ravi Synthetic-02's training.")
    assert out == "Ask [REDACTED_EMPLOYEE_NAME] about [REDACTED_EMPLOYEE_NAME]'s training."


def test_H13_partial_and_embedded_matches_are_left_alone() -> None:
    text = "Asha met Ravi; Synthetic-01 is a code; Asha Synthetic-012 is someone else."
    assert pii.redact(text) == text


def test_H13_too_short_names_are_ignored_so_words_survive() -> None:
    assert pii.redact("Al and all the alerts") == "Al and all the alerts"


def test_H13_names_and_other_identifiers_both_go() -> None:
    out = pii.redact("Asha Synthetic-01, PAN ABCPE1234F, owes ₹1,42,00,000")
    assert "[REDACTED_EMPLOYEE_NAME]" in out and "[REDACTED_PAN]" in out and "₹1,42,00,000" in out


def test_H13_no_names_loaded_means_no_name_masking() -> None:
    pii.set_known_names([])
    assert pii.redact("Asha Synthetic-01") == "Asha Synthetic-01"
