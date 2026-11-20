"""PII v2 recognisers (ADR 0030 §2, scope #57): GSTIN (check digit), UPI ID (PSP handle list),
card (Luhn) and Udyam registration number.

Each kind has one regex and one validator. When Presidio Analyzer imports, the regexes run as
Presidio `PatternRecognizer`s with no NLP engine and no NER model (`nlp_artifacts=None`); when it
does not, or raises at run time, the same regexes and validators run here directly. Either way
every kind is scanned, so text is never stored unscanned (fail closed, ADR 0030 §5).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Payment-service-provider handles seen on NPCI's list of UPI apps (synthetic data only; a handle
# not listed here is not treated as a UPI ID, so ordinary "name@word" text survives).
UPI_HANDLES = (
    "airtel", "apl", "axisbank", "axl", "barodampay", "cnrb", "fbl", "freecharge", "hdfcbank",
    "ibl", "icici", "idfcbank", "jupiteraxis", "kotak", "okaxis", "okhdfcbank", "okicici", "oksbi",
    "paytm", "pnb", "ptaxis", "pthdfc", "ptsbi", "ptyes", "sbi", "unionbank", "upi", "waaxis",
    "wahdfcbank", "yapl", "ybl", "yesbank",
)  # fmt: skip


def gstin_valid(value: str) -> bool:
    """GSTIN check character: base-36 weights 1, 2 alternating over the first 14 characters."""
    v = value.upper()
    if len(v) != 15 or any(c not in _B36 for c in v) or not 1 <= int(v[:2]) <= 38:
        return False
    total = 0
    for i, ch in enumerate(v[:14]):
        product = _B36.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _B36[(36 - total % 36) % 36] == v[14]


def gstin_check_char(first14: str) -> str:
    """The check character for a 14-character GSTIN prefix (tests build valid fixtures with it)."""
    total = 0
    for i, ch in enumerate(first14.upper()):
        product = _B36.index(ch) * (2 if i % 2 else 1)
        total += product // 36 + product % 36
    return _B36[(36 - total % 36) % 36]


def luhn_valid(value: str) -> bool:
    digits = [int(c) for c in value if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


@dataclass(frozen=True)
class Kind:
    name: str  # placeholder kind: [REDACTED_<name>]
    pattern: str
    validate: Callable[[str], bool]
    numeric: bool  # a rupee amount in the same span is never masked (money gate)


KINDS: tuple[Kind, ...] = (
    Kind(
        "GSTIN",
        r"(?<![A-Za-z0-9])\d{2}[A-Za-z]{5}\d{4}[A-Za-z][1-9A-Za-z][Zz][0-9A-Za-z](?![A-Za-z0-9])",
        gstin_valid,
        numeric=False,
    ),
    Kind(
        "UDYAM",
        r"(?i)\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b",
        lambda _: True,
        numeric=False,
    ),
    Kind(
        "UPI",
        r"(?i)(?<![\w.+-])[a-z0-9][\w.-]{1,255}@(?:" + "|".join(UPI_HANDLES) + r")(?![\w.@-])",
        lambda _: True,
        numeric=False,
    ),
    Kind(
        "CARD",
        r"(?<![\d-])\d{4}(?:[ -]?\d{4}){2}(?:[ -]?\d{1,7})?(?![\d-])",
        luhn_valid,
        numeric=True,
    ),
)


def _regex_spans(text: str) -> list[tuple[str, int, int]]:
    out = []
    for kind in KINDS:
        for m in re.finditer(kind.pattern, text):
            if kind.validate(m.group()):
                out.append((kind.name, m.start(), m.end()))
    return out


def _presidio_spans(text: str) -> list[tuple[str, int, int]]:
    out = []
    for kind, recogniser in _RECOGNISERS:
        for r in recogniser.analyze(text, [kind.name], nlp_artifacts=None):
            if kind.validate(text[r.start : r.end]):  # same validator either way
                out.append((kind.name, r.start, r.end))
    return out


def _build() -> tuple[str, list[tuple[Kind, Any]]]:
    try:
        from presidio_analyzer import Pattern, PatternRecognizer
    except Exception:
        return "regex", []
    built = [
        (k, PatternRecognizer(supported_entity=k.name, patterns=[Pattern(k.name, k.pattern, 0.9)]))
        for k in KINDS
    ]
    return "presidio", built


ENGINE, _RECOGNISERS = _build()


def spans(text: str) -> tuple[str, list[tuple[str, int, int]]]:
    """(engine used, [(kind, start, end)]) for the v2 kinds. A Presidio error falls back to the
    regex path for this call, so the text is still scanned."""
    if ENGINE == "presidio":
        try:
            return "presidio", _presidio_spans(text)
        except Exception:
            return "regex", _regex_spans(text)
    return "regex", _regex_spans(text)
