"""PII redaction (NFR-07, ONB-06, VER-03; ARCHITECTURE §8.5).

Applied before every model call and to every reply (llm client), to logs (`set_redactor`), to the
Langfuse mask, and to human free text before it is stored (approver comments, chat).

Aadhaar is redacted only when it is `XXXX XXXX XXXX` or 12 contiguous digits, starts 2-9 and
passes the Verhoeff check, so 12-digit amounts and references survive. A number in money context
(₹/Rs/INR before it, Indian comma grouping, a `/-` suffix or a decimal part) is never masked as
Aadhaar, phone or account. Redact free text only; never engine outputs or ledger fields
(import-linter forbids engines and ledger from importing this module).
Account numbers need an account keyword within 20 characters.
Known ceiling: the IFSC shape (4 letters, 0, 6 alphanumerics) also matches IDs like `INVC0000123`,
so redact free text and model I/O, never structured case files.
The PHONE shape also matches a bare 10-digit figure starting 6-9 (₹60 crore and up in plain
rupee digits). Ledger figures reach prompts as rupees far below that for an MSME; amounts in
paise must never be put in a prompt.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

# Verhoeff tables (dihedral group D5).
_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)
_INV = (0, 4, 3, 2, 1, 5, 6, 7, 8, 9)


def _checksum(digits: str, offset: int) -> int:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[(i + offset) % 8][int(ch)]]
    return c


def verhoeff_valid(digits: str) -> bool:
    return digits.isdigit() and _checksum(digits, 0) == 0


def verhoeff_digit(digits: str) -> str:
    """The check digit to append to `digits`."""
    return str(_INV[_checksum(digits, 1)])


_AADHAAR = re.compile(r"(?<![\d-])[2-9]\d{3}( ?)\d{4}\1\d{4}(?![\d-])")
_CURRENCY_BEFORE = re.compile(r"(?:₹|\bRs\.?|\bINR)\s*$", re.IGNORECASE)
_MONEY_AFTER = re.compile(r"\s*/-|\.\d|,\d")
_NUMERIC = frozenset({"AADHAAR", "ACCOUNT", "PHONE"})


def _is_money(text: str, start: int, end: int) -> bool:
    """The digits at text[start:end] are a rupee amount, not an identifier."""
    digits = re.search(r"\d", text[start:end])
    first = start + digits.start() if digits else start
    return bool(
        _CURRENCY_BEFORE.search(text, 0, first)
        or _MONEY_AFTER.match(text, end)
        or text[first - 1 : first] == ","
    )


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("ACCOUNT", re.compile(r"(?i)\b(?:a/?c|acct|account)\b[^\d\n]{0,20}\d{9,18}\b")),
    ("PAN", re.compile(r"(?i)\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    ("IFSC", re.compile(r"(?i)\b[A-Z]{4}0[A-Z0-9]{6}\b")),
    ("PHONE", re.compile(r"(?<![\w-])(?:\+?91[ -]?)?[6-9]\d{4}[ -]?\d{5}(?!\d)")),
)


@dataclass(frozen=True)
class Hit:
    kind: str
    start: int
    end: int


def find(text: str) -> list[Hit]:
    """Every identifier in `text`, in document order (non-overlapping, earlier kinds win)."""
    hits: list[Hit] = []
    taken: list[tuple[int, int]] = []

    def free(a: int, b: int) -> bool:
        return all(b <= s or a >= e for s, e in taken)

    for m in _AADHAAR.finditer(text):
        if verhoeff_valid(re.sub(r"\D", "", m.group())) and not _is_money(text, *m.span()):
            hits.append(Hit("AADHAAR", m.start(), m.end()))
            taken.append(m.span())
    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if free(*m.span()) and not (kind in _NUMERIC and _is_money(text, *m.span())):
                hits.append(Hit(kind, m.start(), m.end()))
                taken.append(m.span())
    return sorted(hits, key=lambda h: h.start)


def redact(text: str) -> str:
    """Replace each identifier with `[REDACTED_<KIND>]`. Idempotent."""
    for h in reversed(find(text)):
        text = f"{text[: h.start]}[REDACTED_{h.kind}]{text[h.end :]}"
    return text


def redact_value(value: Any) -> Any:
    """`redact` on every string in nested dicts and lists (Langfuse mask, audit payloads)."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, Mapping):
        return {redact(str(k)): redact_value(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact_value(v) for v in value]
    return value
