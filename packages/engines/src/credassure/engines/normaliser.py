"""Parse amounts, rates and dates without float (VER-01).

A value that is not one supported token fails closed. The span is the token
inside the original string, which may have surrounding whitespace.
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext

from credassure.core.money import MONEY

_CRORE = Decimal("10000000")
_LAKH = Decimal("100000")
_HUNDRED = Decimal(100)

_MONEY_RE = re.compile(
    r"""
    ^\s*
    (?P<body>
        (?:₹|Rs\.?|INR)?
        \s*
        (?P<num>\d{1,3}(?:,\d{2})*,\d{3}(?:\.\d+)?|\d+(?:\.\d+)?)
        (?:\s*(?P<unit>crores?|lakhs?|cr\.?|l))?
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_PERCENT_RE = re.compile(
    r"""
    ^\s*
    (?P<body>
        (?P<num>\d+(?:\.\d+)?)
        \s*
        (?:%|percent|per\s+cent)
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_FRACTION_RE = re.compile(
    r"""
    ^\s*
    (?P<body>(?P<num>\d+\.\d+))
    \s*$
    """,
    re.VERBOSE,
)
_ISO_RE = re.compile(r"^\s*(?P<body>(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}))\s*$")
_DMY_RE = re.compile(
    r"^\s*(?P<body>(?P<day>\d{2})(?P<sep>[-/])(?P<month>\d{2})(?P=sep)(?P<year>\d{4}))\s*$"
)


@dataclass(frozen=True, slots=True)
class Parsed[T]:
    value: T
    start: int
    end: int
    raw: str


def format_rate(fraction: Decimal) -> str:
    """Canonical percent text for a fraction. ``0.12`` becomes ``12.00%``."""
    if not isinstance(fraction, Decimal):
        raise TypeError("rates are Decimal fractions")
    with localcontext(MONEY):
        percent = (fraction * _HUNDRED).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{percent}%"


def parse_money(text: str) -> Parsed[Decimal]:
    """Parse one rupee amount. Units: crore/cr and lakh/l (VER-01)."""
    match = _MONEY_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"not a money amount: {text!r}")
    unit = (match.group("unit") or "").lower().rstrip(".")
    with localcontext(MONEY):
        number = Decimal(match.group("num").replace(",", ""))
        if unit in {"crore", "crores", "cr"}:
            number *= _CRORE
        elif unit in {"lakh", "lakhs", "l"}:
            number *= _LAKH
        elif unit:
            raise ValueError(f"unknown money unit: {unit}")
    return _parsed(text, match, number)


def parse_rate(text: str) -> Parsed[Decimal]:
    """Parse a percent or a fraction of 1. A bare integer fails closed (VER-01)."""
    percent = _PERCENT_RE.fullmatch(text)
    if percent is not None:
        with localcontext(MONEY):
            value = Decimal(percent.group("num")) / _HUNDRED
        return _parsed(text, percent, value)
    fraction = _FRACTION_RE.fullmatch(text)
    if fraction is None:
        raise ValueError(f"not a rate: {text!r}")
    with localcontext(MONEY):
        value = Decimal(fraction.group("num"))
    if value > 1:
        raise ValueError(f"fraction above 1 is not a rate: {text!r}")
    return _parsed(text, fraction, value)


def parse_date(text: str) -> Parsed[date]:
    """Parse ISO or day-first ``DD-MM-YYYY`` / ``DD/MM/YYYY``. Month-first fails (VER-01)."""
    iso = _ISO_RE.fullmatch(text)
    dmy = _DMY_RE.fullmatch(text)
    match = iso or dmy
    if match is None:
        raise ValueError(f"not a date: {text!r}")
    try:
        value = date(int(match.group("year")), int(match.group("month")), int(match.group("day")))
    except ValueError as exc:
        raise ValueError(f"not a calendar date: {text!r}") from exc
    return _parsed(text, match, value)


def _parsed[T](text: str, match: re.Match[str], value: T) -> Parsed[T]:
    start = match.start("body")
    end = match.end("body")
    return Parsed(value=value, start=start, end=end, raw=text[start:end])
