"""Finds and redacts Aadhaar, PAN and bank account numbers in chat text (BRD ONB-06, NFR-07).

Redaction runs before text reaches the model, the logs or any store, so the raw numbers are
never kept. Patterns:

  PAN           5 letters, 4 digits, 1 letter (ABCDE1234F), any case
  Aadhaar       12 digits starting 2-9, optionally grouped 4-4-4 with spaces or hyphens,
                or any 12 digits within a few words after "Aadhaar", "Aadhar" or "UID"
  Bank account  9-18 digits within a few words after "account", "a/c", "acct" or "bank",
                or any run of 11-18 digits on its own

Amounts written the Indian way (1,42,00,000) contain commas and are never matched, and a
bare 9-10 digit number with no account word nearby is left alone, so ordinary figures and
phone numbers are not redacted. These are pattern checks: they catch the formats above,
not every way a number can be written.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
# 12 digits, not part of a longer grouped number (so a 14-digit account is not half-matched)
AADHAAR = re.compile(r"(?<![\d-])(?<!\d )[2-9]\d{3}([ -]?)\d{4}\1\d{4}(?![ -]?\d)")
# any 12-digit number the user calls an Aadhaar or UID, even an invalid one
AADHAAR_WITH_WORD = re.compile(r"(?i)\b(?:aadhaar|aadhar|uid)\b[^\d\n]{0,25}(\d{4}[ -]?\d{4}[ -]?\d{4})(?![ -]?\d)")
ACCOUNT_WITH_WORD = re.compile(r"(?i)\b(?:account|a/c|acct|acc\.?|bank)\b[^\d\n]{0,25}(\d(?:[ -]?\d){8,17})(?!\d)")
LONG_DIGITS = re.compile(r"(?<!\d)\d{11,18}(?!\d)")

LABELS = {"PAN": "[REDACTED PAN]", "AADHAAR": "[REDACTED AADHAAR]", "BANK_ACCOUNT": "[REDACTED BANK ACCOUNT]"}


@dataclass(frozen=True)
class PiiMatch:
    kind: str     # PAN, AADHAAR or BANK_ACCOUNT
    start: int
    end: int


def find_pii(text: str) -> list[PiiMatch]:
    found: list[PiiMatch] = []

    def add(kind, start, end):
        if not any(m.start < end and start < m.end for m in found):   # first match wins
            found.append(PiiMatch(kind, start, end))

    for m in PAN.finditer(text):
        add("PAN", m.start(), m.end())
    for m in AADHAAR_WITH_WORD.finditer(text):
        add("AADHAAR", m.start(1), m.end(1))
    for m in AADHAAR.finditer(text):
        add("AADHAAR", m.start(), m.end())
    for m in ACCOUNT_WITH_WORD.finditer(text):
        digits = re.sub(r"\D", "", m.group(1))
        if 9 <= len(digits) <= 18:
            add("BANK_ACCOUNT", m.start(1), m.end(1))
    for m in LONG_DIGITS.finditer(text):
        add("BANK_ACCOUNT", m.start(), m.end())
    return sorted(found, key=lambda m: m.start)


def redact(text: str) -> tuple[str, list[str]]:
    """Returns the text with every match replaced, and the kinds found (each once, in order)."""
    matches = find_pii(text or "")
    out, last, kinds = [], 0, []
    for m in matches:
        out += [text[last:m.start], LABELS[m.kind]]
        last = m.end
        if m.kind not in kinds:
            kinds.append(m.kind)
    out.append((text or "")[last:])
    return "".join(out), kinds


REFUSAL = ("I can't accept Aadhaar, PAN or bank account numbers in chat, so I removed {what} and did not "
           "store {it}. Submit personal documents only through the HR portal.")
_NAMES = {"PAN": "your PAN", "AADHAAR": "your Aadhaar number", "BANK_ACCOUNT": "your bank account number"}


def refusal_message(kinds: list[str]) -> str:
    names = [_NAMES[k] for k in kinds]
    what = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return REFUSAL.format(what=what, it="it" if len(names) == 1 else "them")
