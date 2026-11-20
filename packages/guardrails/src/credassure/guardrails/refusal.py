"""Refusal policy in code, before any model call (CP-03, BRD §14, SUP-08).

Each rule is a regex over the user's message and has a fixed reply that states what the copilot
will not do and points to what it can. Questions the sources cannot answer by construction
(forecasts, foreign rules, credit scores or ratings) get the exact abstention string (CP-02).
Rule order matters: the first match wins.
"""

import re
from collections.abc import Collection
from dataclasses import dataclass
from datetime import date

ABSTAIN = "I can't verify that from the available sources."  # CP-02, exact string

_I = re.IGNORECASE
CASE_ID = re.compile(r"\bCA-\d{4}-\d{4}\b", _I)
OFFER_ID = re.compile(r"\bOF-\d{2}-[A-Z]\b", _I)
YEAR = re.compile(r"\b(20\d\d)\b")


@dataclass(frozen=True)
class Refusal:
    code: str
    text: str
    refused: bool = True


_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "PROBE",
        re.compile(
            r"\bsystem prompt\b|\byour (?:system |hidden )?(?:prompt|instructions)\b"
            r"|\bapi[ _-]?keys?\b|\.env\b|\bjwt\b|\bpasswords?\b|\bsecret keys?\b",
            _I,
        ),
        "The copilot does not reveal its configuration, prompts, keys or credentials. Ask a "
        "question about rules, policies or this case.",
    ),
    (
        "ACCEPTANCE",
        re.compile(
            r"\b(?:accept|sign|submit|execute|e-?sign)\b[^.?!]{0,60}"
            r"\b(?:offer|sanction|loan|agreement|letter|terms|application)s?\b"
            r"|\b(?:accept|sign)\b[^.?!]{0,40}\b(?:lender\w*|bank|OF-\d{2}-[A-Z])"
            r"|\bon (?:our|my) behalf\b",
            _I,
        ),
        "CredAssure cannot accept, sign or submit a lender offer. A finance approver approves "
        "the proposal internally; the MSME chooses its lender outside the system.",
    ),
    (
        "APPROVAL_ODDS",
        re.compile(
            r"\b(?:approv\w*|sanction\w*)\b[^.?!]{0,60}\b(?:probabilit\w*|chances?|odds|likel\w*)\b"
            r"|\b(?:probabilit\w*|chances?|odds|likel\w*)\b[^.?!]{0,60}\b(?:approv\w*|sanction\w*)"
            r"|\b(?:will|would|going to|gonna)\b[^.?!]{0,40}\bapprove\b",
            _I,
        ),
        "CredAssure cannot predict whether a lender will lend or assess creditworthiness. The "
        "offer comparison shows each offer's verified cost and whether it fits the cash flow.",
    ),
    (
        "GATE_OVERRIDE",
        re.compile(
            r"\bmark\b[^.?!]{0,30}\b(?:pass\w*|complet\w*|done)\b|\boverrid\w*|\bbypass\w*"
            r"|\bskip\b[^.?!]{0,30}\b(?:check|gate|stage|verification|onboarding)\b",
            _I,
        ),
        "A failed check cannot be overridden from chat. The stage tracker names the blocker and "
        "the action that clears it; the stage runs again once the record is corrected.",
    ),
    (
        "LEGAL",
        re.compile(
            r"\blegal notice\b|\bsue\b|\blawsuit\b|\blitigat\w*|\blegal advice\b|\btax advice\b",
            _I,
        ),
        "CredAssure gives general, cited information only, not legal or tax advice, and does not "
        "draft notices. Please consult a qualified adviser.",
    ),
    (
        "OTHER_CASE_WORDS",
        re.compile(r"\b(?:another|other|all|every) (?:case|cases|customer|borrower)s?\b", _I),
        "The copilot answers only about this case; other cases' data is not accessible.",
    ),
)
_ABSTAIN_RULES = (
    re.compile(  # forecasts: no source states the future
        r"\bwhat will\b|\bwill (?:apply|be)\b[^.?!]*\b20\d\d\b|\bnext (?:year|quarter|month)\b"
        r"|\bforecast\w*|\bpredict\w*",
        _I,
    ),
    re.compile(r"(?-i:\b(?:US|USA|UK|EU|FCA|SBA|SEC)\b)|\bunited (?:states|kingdom)\b", _I),
    re.compile(r"\bcredit[- ]?(?:score|rating)s?\b|\binternal rating\b|\bcreditworth\w*", _I),
)


def check(message: str, *, case_id: str, offer_ids: Collection[str], as_of: date) -> Refusal | None:
    """The refusal for ``message``, or None when the copilot may try to answer it."""
    for code, rx, text in _RULES:
        if rx.search(message):
            return Refusal(code, text)
    others = {c.upper() for c in CASE_ID.findall(message)} - {case_id.upper()}
    foreign = {o.upper() for o in OFFER_ID.findall(message)} - {o.upper() for o in offer_ids}
    if others or foreign:
        return Refusal("OTHER_CASE", _RULES[-1][2])
    if any(rx.search(message) for rx in _ABSTAIN_RULES) or any(
        int(y) > as_of.year for y in YEAR.findall(message)
    ):
        return Refusal("OUT_OF_SCOPE", ABSTAIN)
    return None
