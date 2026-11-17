"""Normaliser known answers (VER-01). Fifty-plus formats, plus hypothesis round-trips."""

import itertools
from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from credassure.core.money import format_inr
from credassure.engines.normaliser import (
    find_all,
    format_rate,
    parse_date,
    parse_money,
    parse_rate,
)

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
    ("-₹30,00,000", "-3000000"),
    ("\u2212₹30 lakh", "-3000000"),
    ("-30 lakh", "-3000000"),
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
        min_value=Decimal("-1000000000"),
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


SENTENCES: list[tuple[str, list[tuple[str, str, object]]]] = [
    (
        "Peak shortfall ₹1.62 crore in week 9; plus ₹10 lakh buffer, less ₹30 lakh overdraft.",
        [
            ("money", "₹1.62 crore", Decimal("16200000")),
            ("number", "9", Decimal("9")),
            ("money", "₹10 lakh", Decimal("1000000")),
            ("money", "₹30 lakh", Decimal("3000000")),
        ],
    ),
    (
        "Recommended ₹1,42,00,000 at 12% APR (0.12) from 15-11-2026.",
        [
            ("money", "₹1,42,00,000", Decimal("14200000")),
            ("rate", "12%", Decimal("0.12")),
            ("rate", "0.12", Decimal("0.12")),
            ("date", "15-11-2026", date(2026, 11, 15)),
        ],
    ),
    (
        "APR 17.07 per cent; GST 18 percent on fees, disbursed 2026-11-20.",
        [
            ("rate", "17.07 per cent", Decimal("0.1707")),
            ("rate", "18 percent", Decimal("0.18")),
            ("date", "2026-11-20", date(2026, 11, 20)),
        ],
    ),
    (
        "Bridge: \u2212₹30 lakh undrawn OD, Rs. 142L total, 1.42 Cr. need.",
        [
            ("money", "\u2212₹30 lakh", Decimal("-3000000")),
            ("money", "Rs. 142L", Decimal("14200000")),
            ("money", "1.42 Cr.", Decimal("14200000")),
        ],
    ),
    ("No figures here, only Loans and lakhs of words.", []),
    (
        "Due 12/11/2026, invoice INV-2041 for ₹ 2,50,000.",
        [
            ("date", "12/11/2026", date(2026, 11, 12)),
            ("money", "₹ 2,50,000", Decimal("250000")),
        ],
    ),
    ("Version v3 of WC-POL and 9th week stay unparsed.", []),
]


@pytest.mark.parametrize(("text", "expected"), SENTENCES)
def test_VER01_find_all_reads_every_value_with_its_span(
    text: str, expected: list[tuple[str, str, object]]
) -> None:
    found = find_all(text)
    assert [(p.kind, p.raw, p.value) for p in found] == expected
    for p in found:
        assert text[p.start : p.end] == p.raw
    for a, b in itertools.pairwise(found):
        assert a.end <= b.start


@settings(max_examples=40)
@given(
    st.decimals(
        min_value=Decimal("-1000000000"),
        max_value=Decimal("1000000000"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_VER01_find_all_round_trip_in_a_sentence(amount: Decimal) -> None:
    text = f"The need is {format_inr(amount)} this quarter."
    (only,) = find_all(text)
    assert only.kind == "money"
    assert only.value == amount.quantize(Decimal("0.01"))


# Money-auditor findings, 2026-11-05: nothing may slip past, be truncated or be skipped.
ADVERSARIAL: list[tuple[str, list[tuple[str, str]]]] = [
    ("₹10\u201312 lakh", [("number", "10"), ("money", "12 lakh")]),
    ("APR 14\u201316%", [("number", "14"), ("rate", "16%")]),
    ("APR 14.5%\u201316%", [("rate", "14.5%"), ("rate", "16%")]),
    ("between 10-12%", [("number", "10"), ("rate", "12%")]),
    ("Lender A\u201314.5% APR", [("rate", "14.5%")]),
    ("-12%", [("rate", "-12%")]),
    ("rate fell -0.5%", [("rate", "-0.5%")]),
    ("net -12 in week 9", [("number", "-12"), ("number", "9")]),
    ("cash \u22121,62,00,000", [("number", "\u22121,62,00,000")]),
    ("week 9 \u2013₹10 lakh", [("number", "9"), ("money", "₹10 lakh")]),
    ("week 9 - ₹10 lakh", [("number", "9"), ("money", "₹10 lakh")]),
    ("₹1,42,00,0001", [("unparsed", "1,42,00,0001")]),
    ("₹1,42,00,000,000", [("unparsed", "1,42,00,000,000")]),
    ("₹14,200,000", [("unparsed", "14,200,000")]),
    ("₹1,42 lakh", [("unparsed", "1,42")]),
    ("₹10k", [("unparsed", "10")]),
    ("31-02-2026", [("unparsed", "31-02-2026")]),
    ("11/15/2026", [("unparsed", "11/15/2026")]),
    ("0.25 percentage points", [("rate", "0.25 percentage points")]),
    ("0.5 weeks", [("number", "0.5")]),
    ("offer 3 L&T Finance", [("number", "3")]),
    ("₹142 lacs", [("money", "₹142 lacs")]),
    ("15 Nov 2026", [("date", "15 Nov 2026")]),
    ("15.11.2026", [("date", "15.11.2026")]),
    ("1-11-2026", [("date", "1-11-2026")]),
    ("₹\uff11\uff10 lakh", []),
    ("A-14.5%", [("unparsed", "14.5")]),
    ("Rs14,200,000", [("unparsed", "14,200,000")]),
    ("INR1,42,00,0001", [("unparsed", "1,42,00,0001")]),
    ("Rs.-10 lakh", [("money", "Rs.-10 lakh")]),
    ("due 2026/11/15", [("number", "2026"), ("unparsed", "11/15")]),
    ("₹1,42,00,000/12", [("money", "₹1,42,00,000"), ("unparsed", "12")]),
    ("₹1.5 million", [("number", "1.5")]),
    ("₹10 to 12 lakh", [("number", "10"), ("money", "12 lakh")]),
]


@pytest.mark.parametrize(("text", "expected"), ADVERSARIAL)
def test_VER01_find_all_fails_closed(text: str, expected: list[tuple[str, str]]) -> None:
    assert [(p.kind, p.raw) for p in find_all(text)] == expected


def test_VER01_sign_after_currency_is_kept() -> None:
    (only,) = find_all("Rs.-10 lakh")
    assert only.value == Decimal("-1000000")


def test_VER01_find_all_scales_lac_and_point_deltas() -> None:
    lacs, pp = find_all("₹142 lacs and 0.25 pp")
    assert lacs.value == Decimal("14200000")
    assert pp.value == Decimal("0.0025")


# Indian CSV and KFS suffixes (E4 S1): "/-", Rs/INR, lac/L, Cr., "% p.a.".
SUFFIX_MONEY = [
    ("1,42,00,000/-", "14200000"),
    ("₹1,42,00,000/-", "14200000"),
    ("₹ 1,42,00,000 /-", "14200000"),
    ("Rs. 1,42,00,000/-", "14200000"),
    ("Rs 142 lakh", "14200000"),
    ("Rs.1.42 Cr.", "14200000"),
    ("INR 142 lac", "14200000"),
    ("INR 1,42,00,000/-", "14200000"),
    ("142L/-", "14200000"),
    ("142 lacs/-", "14200000"),
    ("1.42 crore /-", "14200000"),
    ("1.42 Cr./-", "14200000"),
    ("Rs 10,000/-", "10000"),
    ("14200000/-", "14200000"),
]
SUFFIX_RATE = [
    ("12.50 % p.a.", "0.125"),
    ("11.5% p.a.", "0.115"),  # Phase 10b item 5, the user's example
    ("12.50%p.a.", "0.125"),
    ("12% pa", "0.12"),
    ("12 % per annum", "0.12"),
    ("12.5 percent per annum", "0.125"),
    ("9.25 %  p.a", "0.0925"),
    ("10.75% P.A.", "0.1075"),
    ("18 %", "0.18"),
]


@pytest.mark.parametrize(("text", "expected"), SUFFIX_MONEY)
def test_VER01_parse_money_indian_suffixes(text: str, expected: str) -> None:
    assert parse_money(text).value == Decimal(expected)


@pytest.mark.parametrize(("text", "expected"), SUFFIX_RATE)
def test_VER01_parse_rate_indian_suffixes(text: str, expected: str) -> None:
    assert parse_rate(text).value == Decimal(expected)


@pytest.mark.parametrize("text", ["/-", "1,42,00,000/-/-", "12 p.a.", "p.a.", "12% p.a. p.a."])
def test_VER01_suffixes_alone_or_doubled_fail_closed(text: str) -> None:
    for parse in (parse_money, parse_rate):
        with pytest.raises(ValueError):
            parse(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("need ₹1,42,00,000/- now", [("money", "₹1,42,00,000/-")]),
        ("rate 12.50 % p.a. fixed", [("rate", "12.50 % p.a.")]),
        ("at 12% per annum.", [("rate", "12% per annum")]),
    ],
)
def test_VER01_find_all_spans_cover_suffixes(text: str, expected: list[tuple[str, str]]) -> None:
    assert [(p.kind, p.raw) for p in find_all(text)] == expected


@pytest.mark.parametrize("text", ["12% p.m.", "1.5 % per month", "3% p.q.", "2% pm"])
def test_VER01_non_annual_rate_is_unparsed_not_read_as_annual(text: str) -> None:
    assert [p.kind for p in find_all(text)] == ["unparsed"]


def test_VER01_csv_cell_with_rupee_suffix_reaches_the_cash_engine() -> None:
    """Phase 10b item 5 (E4 S1): a CSV amount cell written "1,42,00,000/-" is read, not refused."""
    from credassure.engines.cashflow import money

    assert money("1,42,00,000/-") == Decimal("14200000")
