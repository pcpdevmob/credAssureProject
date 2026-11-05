"""Parse amounts, rates and dates without float (VER-01).

A value that is not one supported token fails closed. The span is the token
inside the original string, which may have surrounding whitespace.
``find_all`` scans free text (agent narratives) and returns every value it reads.
Digits it cannot read come back as ``unparsed`` so the Critic fails closed.
Only ASCII digits count (a full-width or Arabic-Indic digit is not a number here).
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Literal

from credassure.core.money import MONEY

_CRORE = Decimal("10000000")
_LAKH = Decimal("100000")
_HUNDRED = Decimal(100)
_NUM = r"[0-9]{1,3}(?:,[0-9]{2})*,[0-9]{3}(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?"
_UNIT = r"crores?|lakhs?|lacs?|cr\.?|l"
_MONTHS = r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
_MONTH_NO = {name: i for i, name in enumerate(_MONTHS.split("|"), start=1)}

_MONEY_RE = re.compile(
    rf"""
    ^\s*
    (?P<body>
        (?P<sign>[\-\u2212\u2013])?
        (?:₹|Rs\.?|INR)?
        \s*
        (?P<sign2>[\-\u2212])?
        (?P<num>{_NUM})
        (?:\s*(?P<unit>{_UNIT}))?
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_PERCENT_RE = re.compile(
    r"""
    ^\s*
    (?P<body>
        (?P<sign>[\-\u2212])?
        (?P<num>[0-9]+(?:\.[0-9]+)?)
        \s*
        (?:%|percent|per\s+cent)
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)
_FRACTION_RE = re.compile(r"^\s*(?P<body>(?P<num>[0-9]+\.[0-9]+))\s*$")
_ISO_RE = re.compile(r"^\s*(?P<body>(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2}))\s*$")
_DMY_RE = re.compile(
    r"^\s*(?P<body>(?P<day>[0-9]{1,2})(?P<sep>[-/.])(?P<month>[0-9]{1,2})(?P=sep)"
    r"(?P<year>[0-9]{4}))\s*$"
)
_NAMED_RE = re.compile(
    rf"^\s*(?P<body>(?P<day>[0-9]{{1,2}})\s+(?P<mon>{_MONTHS})[a-z]*\.?,?\s+(?P<year>[0-9]{{4}}))\s*$",
    re.IGNORECASE,
)

# A sign only counts when it does not follow a number ("10-12%" is a range).
# An en dash is never a sign in free text: it is a separator ("week 9 \u2013 ₹10 lakh").
_SIGN = r"(?:(?<![0-9%])(?<![0-9%]\s)[\-\u2212])?"
# No partial reads: "₹1,42,00,0001" or "₹14,200,000" must not stop early.
_END = r"(?![0-9,._]*[0-9]|\w)"
# "₹10\u201312 lakh" is a range in lakh: never read its left end as ₹10.
_NOT_RANGE = r"(?!\s*(?:[\-\u2013]|to)\s*[0-9])"
# "₹1.5 million" is not ₹1.5: an unknown scale word drops the currency read.
_NO_OTHER_SCALE = r"(?!\s*(?:million|mn|billion|bn|thousand|k)(?!\w))"

# Scanner for free text. Order matters: dates, then rates, then money with a
# currency mark or unit, then a bare number. The lookbehinds stop it starting
# inside a number or an identifier such as "INV-2041".
_SCAN_RE = re.compile(
    rf"""
    (?<![\w.,/])(?<![A-Za-z]-)
    (?:
        (?P<date>(?:[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}
                   |[0-9]{{1,2}}(?P<sep>[-/.])[0-9]{{1,2}}(?P=sep)[0-9]{{4}}
                   |[0-9]{{1,2}}\s+(?:{_MONTHS})[a-z]*\.?,?\s+[0-9]{{4}})(?![0-9]))
      | (?P<pp>{_SIGN}[0-9]+(?:\.[0-9]+)?\s*(?:pp|percentage\s+points?)(?!\w))
      | (?P<rate>{_SIGN}[0-9]+(?:\.[0-9]+)?\s*(?:%|percent(?!\w)|per\s+cent(?!\w)))
      | (?P<money>{_SIGN}
            (?:(?:₹|Rs\.?|INR)\s*[\-\u2212]?(?:{_NUM})
                (?:\s*(?:{_UNIT})(?![\w&])|{_END}{_NOT_RANGE}{_NO_OTHER_SCALE})
              | (?:{_NUM})\s*(?:{_UNIT})(?![\w&])))
      | (?P<number>{_SIGN}(?:{_NUM}){_END})
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
_PP_UNIT_RE = re.compile(r"\s*(?:pp|percentage\s+points?)$", re.IGNORECASE)
_DIGIT_RUN_RE = re.compile(r"[0-9]+(?:[.,/:\-][0-9]+)*")
_DIGIT_PIECE_RE = re.compile(r"[0-9](?:[^ ]*[0-9])?")
_ID_BEFORE_RE = re.compile(r"[A-Za-z]-?$")
_CURRENCY_BEFORE_RE = re.compile(r"(?:₹|Rs\.?|INR)\s*[\-\u2212]?$", re.IGNORECASE)
_ORDINAL_AFTER_RE = re.compile(r"(?:st|nd|rd|th)(?!\w)", re.IGNORECASE)

Kind = Literal["money", "rate", "date", "number", "unparsed"]


@dataclass(frozen=True, slots=True)
class Parsed[T]:
    value: T
    start: int
    end: int
    raw: str
    kind: Kind


def format_rate(fraction: Decimal) -> str:
    """Canonical percent text for a fraction. ``0.12`` becomes ``12.00%``."""
    if not isinstance(fraction, Decimal):
        raise TypeError("rates are Decimal fractions")
    with localcontext(MONEY):
        percent = (fraction * _HUNDRED).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{percent}%"


def parse_money(text: str) -> Parsed[Decimal]:
    """Parse one rupee amount. Units: crore/cr and lakh/lac/l (VER-01)."""
    match = _MONEY_RE.fullmatch(text)
    if match is None:
        raise ValueError(f"not a money amount: {text!r}")
    unit = (match.group("unit") or "").lower().rstrip(".")
    with localcontext(MONEY):
        number = Decimal(match.group("num").replace(",", ""))
        if unit in {"crore", "crores", "cr"}:
            number *= _CRORE
        elif unit in {"lakh", "lakhs", "lac", "lacs", "l"}:
            number *= _LAKH
        elif unit:
            raise ValueError(f"unknown money unit: {unit}")
        if match.group("sign") or match.group("sign2"):
            number = -number
    return _parsed(text, match, number, "money")


def parse_rate(text: str) -> Parsed[Decimal]:
    """Parse a percent or a fraction of 1. A bare integer fails closed (VER-01)."""
    percent = _PERCENT_RE.fullmatch(text)
    if percent is not None:
        with localcontext(MONEY):
            value = Decimal(percent.group("num")) / _HUNDRED
            if percent.group("sign"):
                value = -value
        return _parsed(text, percent, value, "rate")
    fraction = _FRACTION_RE.fullmatch(text)
    if fraction is None:
        raise ValueError(f"not a rate: {text!r}")
    with localcontext(MONEY):
        value = Decimal(fraction.group("num"))
    if value > 1:
        raise ValueError(f"fraction above 1 is not a rate: {text!r}")
    return _parsed(text, fraction, value, "rate")


def parse_date(text: str) -> Parsed[date]:
    """Parse ISO, day-first ``D-M-YYYY`` (``-``, ``/`` or ``.``) or ``15 Nov 2026``.

    Month-first fails closed (VER-01).
    """
    match = _ISO_RE.fullmatch(text) or _DMY_RE.fullmatch(text)
    if match is not None:
        year, month, day = match.group("year"), match.group("month"), match.group("day")
    else:
        match = _NAMED_RE.fullmatch(text)
        if match is None:
            raise ValueError(f"not a date: {text!r}")
        year, day = match.group("year"), match.group("day")
        month = str(_MONTH_NO[match.group("mon").lower()])
    try:
        value = date(int(year), int(month), int(day))
    except ValueError as exc:
        raise ValueError(f"not a calendar date: {text!r}") from exc
    return _parsed(text, match, value, "date")


Found = Parsed[Decimal] | Parsed[date] | Parsed[str]


def find_all(text: str) -> list[Found]:
    """Every amount, rate, date and number in ``text``, in order, with spans (VER-01).

    A bare decimal at most 1 (``0.12``) reads as a rate unless a word follows it.
    Any other bare number stays ``number`` so the Critic can flag it as unsourced.
    Digits that are not part of a value or an identifier (``INV-2041``, ``v3``,
    ``9th``) come back as ``unparsed``: an invalid date, a truncated amount, a
    western-grouped figure. The Critic must treat those as unmatched.
    """
    found: list[Found] = []
    for match in _SCAN_RE.finditer(text):
        kind = match.lastgroup
        raw = match.group(0)
        start, end = match.start(), match.end()
        item: Found
        if kind == "date":
            try:
                item = _at(parse_date(raw), start)
            except ValueError:  # 31-02-2026, 11/15/2026: fail closed
                item = Parsed(value=raw, start=start, end=end, raw=raw, kind="unparsed")
        elif kind == "pp":
            number = _PP_UNIT_RE.sub("", raw).replace("\u2212", "-")
            with localcontext(MONEY):
                value = Decimal(number) / _HUNDRED
            item = Parsed(value=value, start=start, end=end, raw=raw, kind="rate")
        elif kind == "rate":
            item = _at(parse_rate(raw), start)
        elif kind == "money":
            item = _at(parse_money(raw), start)
        else:
            item = _bare_number(text, raw, start, end)
        found.append(item)
    found.extend(_leftover_digits(text, found))
    return sorted(found, key=lambda p: p.start)


def _bare_number(text: str, raw: str, start: int, end: int) -> Found:
    word_follows = text[end:].lstrip()[:1].isalpha()
    if not word_follows:
        try:
            return _at(parse_rate(raw), start)
        except ValueError:
            pass
    with localcontext(MONEY):
        number = Decimal(raw.replace(",", "").replace("\u2212", "-"))
    return Parsed(value=number, start=start, end=end, raw=raw, kind="number")


def _leftover_digits(text: str, found: list[Found]) -> list[Found]:
    covered = [False] * len(text)
    for p in found:
        covered[p.start : p.end] = [True] * (p.end - p.start)
    leftovers: list[Found] = []
    for run in _DIGIT_RUN_RE.finditer(text):
        before, after = text[: run.start()], text[run.end() :]
        identifier = (
            _ID_BEFORE_RE.search(before)
            and not _CURRENCY_BEFORE_RE.search(before)
            and not after.lstrip().startswith("%")
        )
        if identifier or _ORDINAL_AFTER_RE.match(after):
            continue
        # Report every uncovered piece, so "₹1,42,00,000/12" keeps its "/12".
        for piece in _DIGIT_PIECE_RE.finditer(
            "".join(" " if covered[i] else text[i] for i in range(run.start(), run.end()))
        ):
            start = run.start() + piece.start()
            end = run.start() + piece.end()
            raw = text[start:end]
            leftovers.append(Parsed(value=raw, start=start, end=end, raw=raw, kind="unparsed"))
    return leftovers


def _at[T](parsed: Parsed[T], offset: int) -> Parsed[T]:
    return Parsed(
        value=parsed.value,
        start=parsed.start + offset,
        end=parsed.end + offset,
        raw=parsed.raw,
        kind=parsed.kind,
    )


def _parsed[T](text: str, match: re.Match[str], value: T, kind: Kind) -> Parsed[T]:
    start = match.start("body")
    end = match.end("body")
    return Parsed(value=value, start=start, end=end, raw=text[start:end], kind=kind)
