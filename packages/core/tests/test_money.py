"""Money helpers (BR-05, scope #8). Exact inside, display is separate."""

from decimal import Decimal

import pytest

from credassure.core.money import format_inr, from_paise, round_up_to_lakh, to_paise


def test_BR05_format_inr_uses_indian_grouping() -> None:
    assert format_inr(Decimal("14200000")) == "₹1,42,00,000"
    assert format_inr(Decimal("1000")) == "₹1,000"
    assert format_inr(Decimal("100000")) == "₹1,00,000"
    assert format_inr(Decimal("100")) == "₹100"
    assert format_inr(Decimal("0")) == "₹0"


def test_BR05_format_inr_shows_paise_only_when_present() -> None:
    assert format_inr(Decimal("14200000.50")) == "₹1,42,00,000.50"
    assert format_inr(Decimal("14200000.504")) == "₹1,42,00,000.50"
    assert format_inr(Decimal("14200000.505")) == "₹1,42,00,000.51"
    assert format_inr(Decimal("0.5")) == "₹0.50"


def test_BR05_to_paise_rounds_half_up() -> None:
    assert to_paise(Decimal("10")) == 1000
    assert to_paise(Decimal("1.005")) == 101
    assert to_paise(Decimal("1.004")) == 100
    assert from_paise(1000) == Decimal("10.00")
    assert from_paise(to_paise(Decimal("14200000.50"))) == Decimal("14200000.50")


def test_BR05_round_up_to_lakh_keeps_an_exact_multiple() -> None:
    assert round_up_to_lakh(Decimal("0")) == Decimal("0")
    assert round_up_to_lakh(Decimal("100000")) == Decimal("100000")
    assert round_up_to_lakh(Decimal("14200000")) == Decimal("14200000")


def test_BR05_round_up_to_lakh_lifts_one_rupee_over_the_boundary() -> None:
    assert round_up_to_lakh(Decimal("1")) == Decimal("100000")
    assert round_up_to_lakh(Decimal("14200001")) == Decimal("14300000")


def test_BR05_round_up_to_lakh_rejects_a_negative() -> None:
    with pytest.raises(ValueError):
        round_up_to_lakh(Decimal("-1"))


def test_BR05_money_helpers_reject_float() -> None:
    with pytest.raises(TypeError):
        format_inr(1.5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        to_paise(1.5)  # type: ignore[arg-type]
