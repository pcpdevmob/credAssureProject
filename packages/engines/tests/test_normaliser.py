"""Normaliser known answers (VER-01). Fifty-plus formats, plus hypothesis round-trips."""

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from credassure.core.money import format_inr
from credassure.engines.normaliser import format_rate, parse_date, parse_money, parse_rate

MONEY = [
    ("₹1,42,00,000", "14200000"),
    ("₹ 1,42,00,000", "14200000"),
    ("1,42,00,000", "14200000"),
    ("1.42 crore", "14200000"),
    ("1.42 crores", "14200000"),
    ("142 lakh", "14200000"),
    ("142 lakhs", "14200000"),
    ("1.42 Cr", "14200000"),
    ("1.42 Cr.", "14200000"),
    ("1.42 cr", "14200000"),
    ("Rs. 142L", "14200000"),
    ("Rs. 142 L", "14200000"),
    ("Rs 142L", "14200000"),
    ("₹ 142 L", "14200000"),
    ("₹142 L", "14200000"),
    ("142L", "14200000"),
    ("₹10,000", "10000"),
    ("₹0", "0"),
    ("0.5 crore", "5000000"),
    ("1 lakh", "100000"),
    ("₹1,00,000", "100000"),
    ("2.5 lakh", "250000"),
    ("₹1,42,00,000.50", "14200000.50"),
    ("₹ 142L", "14200000"),
    ("10 crore", "100000000"),
    ("₹99,999", "99999"),
    ("1.00 crore", "10000000"),
    ("Rs.1.42Cr", "14200000"),
    ("₹1", "1"),
    ("3 lakhs", "300000"),
    ("₹2,50,000", "250000"),
    ("0 lakh", "0"),
    ("Rs. 10 Cr.", "100000000"),
]

RATES = [
    ("12%", "0.12"),
    ("12 %", "0.12"),
    ("12 percent", "0.12"),
    ("12 per cent", "0.12"),
    ("0.12", "0.12"),
    ("8.15%", "0.0815"),
    ("0.0815", "0.0815"),
    ("17.07%", "0.1707"),
    ("0%", "0"),
    ("12.5 percent", "0.125"),
    ("0.00", "0.00"),
    ("18 per cent", "0.18"),
]

DATES = [
    ("2026-11-12", date(2026, 11, 12)),
    ("12-11-2026", date(2026, 11, 12)),
    ("12/11/2026", date(2026, 11, 12)),
    ("01-01-2026", date(2026, 1, 1)),
    ("2026-11-15", date(2026, 11, 15)),
    ("15/11/2026", date(2026, 11, 15)),
    ("29-02-2024", date(2024, 2, 29)),
    ("31-12-2026", date(2026, 12, 31)),
    ("  12-11-2026  ", date(2026, 11, 12)),
]


@pytest.mark.parametrize(("text", "expected"), MONEY)
def test_VER01_parse_money(text: str, expected: str) -> None:
    parsed = parse_money(text)
    assert parsed.value == Decimal(expected)
    assert parsed.raw == text.strip()
    assert text[parsed.start : parsed.end] == parsed.raw


@pytest.mark.parametrize(("text", "expected"), RATES)
def test_VER01_parse_rate(text: str, expected: str) -> None:
    parsed = parse_rate(text)
    assert parsed.value == Decimal(expected)
    assert parsed.raw == text.strip()
    assert text[parsed.start : parsed.end] == parsed.raw


@pytest.mark.parametrize(("text", "expected"), DATES)
def test_VER01_parse_date(text: str, expected: date) -> None:
    parsed = parse_date(text)
    assert parsed.value == expected
    assert parsed.raw == text.strip()
    assert text[parsed.start : parsed.end] == parsed.raw


@pytest.mark.parametrize("text", ["12", ""])
def test_VER01_bare_or_empty_is_not_a_rate_or_date(text: str) -> None:
    with pytest.raises(ValueError):
        parse_rate(text)
    with pytest.raises(ValueError):
        parse_date(text)


@pytest.mark.parametrize("text", ["11/13/2026", "29-02-2026", "2026/11/12", "November 12, 2026"])
def test_VER01_rejects_a_date_that_is_not_iso_or_day_first(text: str) -> None:
    with pytest.raises(ValueError):
        parse_date(text)


def test_VER01_unknown_money_unit_fails_closed() -> None:
    with pytest.raises(ValueError):
        parse_money("1.42 million")


def test_VER01_padded_money_span_skips_whitespace() -> None:
    parsed = parse_money("  ₹1,42,00,000  ")
    assert parsed.start == 2
    assert parsed.end == 14
    assert parsed.raw == "₹1,42,00,000"


@settings(max_examples=40)
@given(
    st.decimals(
        min_value=0,
        max_value=Decimal("1000000000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_VER01_money_round_trip(amount: Decimal) -> None:
    parsed = parse_money(format_inr(amount))
    assert parsed.value == amount.quantize(Decimal("0.01"))


@settings(max_examples=30)
@given(
    st.decimals(
        min_value=0, max_value=Decimal("1"), places=4, allow_nan=False, allow_infinity=False
    )
)
def test_VER01_rate_round_trip(fraction: Decimal) -> None:
    parsed = parse_rate(format_rate(fraction))
    assert parsed.value == fraction.quantize(Decimal("0.0001"))


@settings(max_examples=20)
@given(st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)))
def test_VER01_date_round_trip(day: date) -> None:
    parsed = parse_date(day.isoformat())
    assert parsed.value == day
