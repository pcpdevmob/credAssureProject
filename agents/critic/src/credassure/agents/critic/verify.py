"""verify_claims (VER-01..04, design-detail §2.4.5): the Critic's checks on generated text.

Pure and model-free (the model never checks itself). Inputs are the case's latest ledger facts,
the code-rendered slot values the text was built from, and a citation resolver.

- VER-01 numbers: every amount, rate, date and bare number either sits inside a code-rendered slot
  value or equals a ledger fact (money to ₹1, rates to 0.01 pp, dates exactly). A slot whose key is
  a ledger key must still equal the current fact (a stale narrative). Unparsed digits are critical.
- Reason containment (model text only): every sentence carries a slot value, and what is left after
  removing the slot values has no causal connective and no quality claim. Reasons come only from
  code-computed slots (e.g. "would push cash below the minimum buffer in week 12"). A sentence
  that cites a passage is anchored by that passage instead (copilot, 9e).
- Grounded wording (9e): inside a citing sentence, a banned or reason word is allowed only when the
  same words appear in a passage it cites ("guaranteed amount" quoted from R-CG-02 passes; "will be
  approved" is in no source, so it is still blocked).
- VER-02 citations: each [R-…]/[KFS-…]/[POL-…]/[FAQ-…]/[HELP-…] (help, ADR 0035) resolves to an
  indexed passage that is in force, allowed and of this case; every figure in the citing sentence
  appears in the passage.
- VER-03 banned content (banned.yaml, S-VER-02) and personal identifiers.
- VER-04 report sections (``report_completeness``).
"""

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import yaml

from credassure.core.blockers import BlockerCode
from credassure.core.enums import Stage
from credassure.core.findings import CriticFinding, FindingSeverity
from credassure.engines.normaliser import find_all
from credassure.security import pii

# id -> (status, passage text); status in {"ok", "missing", "superseded", "filtered"}
Resolve = Callable[[Sequence[str]], Mapping[str, tuple[str, str]]]

MONEY_TOL = Decimal("1")  # VER-01: amounts to ₹1
RATE_TOL = Decimal("0.00005")  # half of 0.01 pp: a two-decimal display of the fact
CITE = re.compile(r"\[((?:R|KFS|POL|FAQ|HELP)-[A-Za-z0-9][\w.#:\-]*)\]")
SENTENCE = re.compile(r"(?<=[.!?;])\s+|\n+")
CAUSAL = re.compile(
    r"\b(?:because|due to|since|as a result|owing to|given that|thanks to|which means|means that"
    r"|therefore|thus|hence|so that|in order to|leading to|resulting in|driven by|caused by"
    r"|reflect(?:s|ing)?|on account of)\b",
    re.IGNORECASE,
)
QUALITY = re.compile(
    r"\b(?:flexib\w*|better|best|worse|worst|attractiv\w*|competitiv\w*|favou?rabl\w*|reliab\w*"
    r"|ideal|suitabl\w*|safer|safest|safe|risk\w*|good|great|excellent|poor|strong"
    r"|weak|optimal|preferr?\w*|advantag\w*|benefit\w*|smooth\w*|easier|easy|transparen\w*"
    r"|trust\w*|reputa\w*|quick\w*|faster|fast|convenien\w*|value for money|wise|prudent"
    r"|sensible|significant\w*|substantial\w*|healthy|comfortabl\w*|generous|hidden)\b",
    re.IGNORECASE,
)
_NUMBER_UNITS = frozenset({"week", "weeks", "count", "version", "days", "months"})
_CRITICAL = FindingSeverity.CRITICAL


@dataclass(frozen=True)
class Fact:
    value: str
    unit: str


@dataclass(frozen=True)
class Banned:
    version: str
    all: tuple[tuple[str, re.Pattern[str]], ...]
    model_only: Mapping[str, tuple[tuple[str, re.Pattern[str]], ...]]


@cache
def banned() -> Banned:
    data = yaml.safe_load(Path(__file__).with_name("banned.yaml").read_text(encoding="utf-8"))

    def compile_(group: Mapping[str, str]) -> tuple[tuple[str, re.Pattern[str]], ...]:
        return tuple((name, re.compile(rx, re.IGNORECASE)) for name, rx in group.items())

    return Banned(
        str(data["version"]),
        compile_(data["all"]),
        {stage: compile_(group) for stage, group in (data.get("model_only") or {}).items()},
    )


def _finding(
    code: BlockerCode, message: str, stage: Stage | None, span: str | None = None
) -> CriticFinding:
    return CriticFinding(
        severity=_CRITICAL, code=code, message=message, span=span, target_stage=stage
    )


def _dec(text: str) -> Decimal | None:
    try:
        return Decimal(text)
    except ArithmeticError:
        return None


def _matches(kind: str, value: object, facts: Mapping[str, Fact]) -> bool:
    for f in facts.values():
        if kind == "date":
            if isinstance(value, date) and f.value == value.isoformat():
                return True
            continue
        got = _dec(f.value)
        if got is None or not isinstance(value, Decimal):
            continue
        if kind == "money" and f.unit == "INR" and abs(got - value) < MONEY_TOL:
            return True
        if kind == "rate" and f.unit == "rate" and abs(got - value) <= RATE_TOL:
            return True
        if kind == "number" and f.unit in _NUMBER_UNITS and got == value:
            return True
    return False


def _spans(text: str, values: Iterable[str]) -> list[tuple[int, int]]:
    """Where code-rendered slot values occur in the text (whole tokens only)."""
    out = []
    for v in sorted({v for v in values if v.strip()}, key=len, reverse=True):
        rx = re.compile(r"(?<![\w.,])" + re.escape(v) + r"(?![\w])")
        out += [(m.start(), m.end()) for m in rx.finditer(text)]
    return out


def _inside(start: int, end: int, spans: Sequence[tuple[int, int]]) -> bool:
    return any(a <= start and end <= b for a, b in spans)


def _numbers(
    text: str,
    facts: Mapping[str, Fact],
    slot_spans: Sequence[tuple[int, int]],
    stage: Stage | None,
    *,
    model: bool = False,
) -> list[CriticFinding]:
    """Model text: every figure must sit inside a code-rendered slot (a figure that merely equals
    some other fact of the case is still the model's own). Code text: it must equal a fact."""
    out = []
    for h in find_all(text):
        if _inside(h.start, h.end, slot_spans):
            continue
        shown = text[h.start : h.end]
        if model or h.kind == "unparsed" or not _matches(h.kind, h.value, facts):
            out.append(
                _finding(
                    BlockerCode.VER_UNMATCHED_NUMBER,
                    f"{shown!r} is not a ledger fact",
                    stage,
                    shown,
                )
            )
    return out


def _stale(
    slots: Mapping[str, str], facts: Mapping[str, Fact], stage: Stage | None
) -> list[CriticFinding]:
    """A slot named after a ledger key must still equal that fact (the text may be outdated)."""
    out = []
    for key, rendered in slots.items():
        fact = facts.get(key)
        if fact is None:
            continue
        hits = [h for h in find_all(rendered) if h.kind != "unparsed"]
        if len(hits) == 1 and not _matches(hits[0].kind, hits[0].value, {key: fact}):
            out.append(
                _finding(
                    BlockerCode.VER_UNMATCHED_NUMBER,
                    f"{rendered!r} no longer equals ledger {key}",
                    stage,
                    rendered,
                )
            )
    return out


def _reasons(
    text: str,
    slots: Mapping[str, str],
    stage: Stage | None,
    grounded: Callable[[int, int, str], bool] = lambda a, b, w: False,
) -> list[CriticFinding]:
    """Slot spans are found on the whole text first, so a sentence break never cuts inside a
    code-rendered value (a next action such as "finish the course; HR records the completion")."""
    spans = _spans(text, slots.values())
    anchor_spans = _spans(text, [v for k, v in slots.items() if not k.startswith("cmp.")])
    cuts = [m for m in SENTENCE.finditer(text) if not _inside(m.start(), m.end(), spans)]
    bounds = [0, *(x for m in cuts for x in (m.start(), m.end())), len(text)]
    out = []
    for lo, hi in zip(bounds[::2], bounds[1::2], strict=True):
        if not text[lo:hi].strip():
            continue
        rest = "".join(
            " " if any(a <= i < b for a, b in spans) else ch for i, ch in enumerate(text[lo:hi], lo)
        )
        has_anchor = any(lo <= a and b <= hi for a, b in anchor_spans) or grounded(lo, hi, "")
        words = [m for rx in (CAUSAL, QUALITY) for m in rx.finditer(rest)]
        if not has_anchor or any(not grounded(lo + m.start(), lo + m.end(), m[0]) for m in words):
            out.append(
                _finding(
                    BlockerCode.VER_UNSUPPORTED_REASON,
                    "a sentence states a reason or judgement that no code-computed slot gives",
                    stage,
                    text[lo:hi].strip()[:200],
                )
            )
    return out


_TERMS = re.compile(r"(?:guaranteed|sanctioned)\s+(?:amount|portion|limits?|cover)\b", re.I)
# Who approves inside the company (the approval matrix), never whether anything will be approved:
# only these word forms, never "approve"/"approved" ("will approve", "is approved" are predictions).
_AUTHORITY = re.compile(r"approv(?:es|als?|ers?)\b", re.I)
# A sentence about a lender, a bank or a sanction is never excused, whatever it cites.
_LENDERISH = re.compile(r"\b(?:lender\w*|bank\w*|nbfc\w*|sanction\w*|loan offer\w*)\b", re.I)
# Team-owned internal policy collection (WC-POL, approval matrix, FAQ); public and KFS text never.
_POLICY_IDS = ("POL-", "FAQ-")
# P11 K2: rules whose words a copilot answer may quote word for word from a cited public or policy
# passage (statutes say "day of acceptance", "date immediately following", "weighted average
# lending rate"). Approval predictions, lender choice and gate words are never excused this way.
_QUOTABLE_RULES = frozenset({"acceptance", "false_urgency", "invented_rate"})
# Lender-controlled (KFS, where injection plants live) and product-help text never grounds a quote.
_UNQUOTABLE_IDS = ("KFS-", "HELP-")
# Acceptance wording about a loan, borrower, offer, agreement or credit is never a quote to excuse.
_DEALISH = re.compile(
    r"\b(?:loan\w*|borrow\w*|offer\w*|agreement\w*|contract\w*|facilit\w*|credit\w*)\b", re.I
)
# Words about the case or its people: a quote never applies to them ("the proposal is accepted by
# the Director", "the deadline is today for the proposal"; security review K2).
_CASEISH = re.compile(
    r"\b(?:proposal\w*|application\w*|applicant\w*|director\w*|vp|approver\w*|cases?)\b", re.I
)
# A sentence addressed to the user or about this case is advice, not a quote.
_ADDRESSED = re.compile(
    r"\b(?:you|your|yours|we|our|ours|us|this (?:case|proposal|loan|offer))\b", re.I
)


def _banned(
    text: str,
    *,
    model: bool,
    stage: Stage | None,
    grounded: Callable[[int, int, str], bool] = lambda a, b, w: False,
    authority: Callable[[int, int, str], bool] = lambda a, b, w: False,
    quoted: Callable[[int, int, str], bool] = lambda a, b, r: False,
) -> list[CriticFinding]:
    b = banned()
    rules = list(b.all)
    if model and stage is not None:
        rules += b.model_only.get(stage.value, ())

    def excused(m: re.Match[str], rule: str) -> bool:
        # Only a quoted noun term ("guaranteed amount") is excused, never a prediction or
        # acceptance phrase, however common its word pair is in passages (9e security review).
        term = _TERMS.match(text, m.start())
        if term is not None and grounded(m.start(), term.end(), term[0]):
            return True
        # An approval-matrix fact ("the VP, Finance approves proposals above ...") stated by a cited
        # internal policy passage that uses the same word (P11, VER-03 false positive).
        word = _AUTHORITY.fullmatch(m[0])
        if word is not None and authority(m.start(), m.end(), word[0]):
            return True
        # P11 K2: statute or rate wording quoted word for word from a cited passage.
        return rule in _QUOTABLE_RULES and quoted(m.start(), m.end(), rule)

    out = []
    for name, rx in rules:
        m = next((m for m in rx.finditer(text) if not excused(m, name)), None)
        if m:
            out.append(
                _finding(
                    BlockerCode.VER_BANNED_CONTENT,
                    f"{name} wording (banned list {b.version})",
                    stage,
                    m.group(0),
                )
            )
    return out


def _citations(
    text: str, found: Mapping[str, tuple[str, str]] | None, stage: Stage | None
) -> list[CriticFinding]:
    cited = [(m.group(1), m.start()) for m in CITE.finditer(text)]
    if not cited:
        return []
    if found is None:
        return [_finding(BlockerCode.VER_BAD_CITATION, "no source library to check", stage)]
    out = []
    sentences = _sentences_with_offsets(text)

    def sentence_of(pos: int) -> str:
        return next(s for a, s in sentences if a <= pos < a + len(s))

    for cid, pos in cited:
        status = found.get(cid, ("missing", ""))[0]
        if status == "superseded":
            out.append(
                _finding(BlockerCode.VER_SUPERSEDED_SOURCE, f"{cid} is not in force", stage, cid)
            )
            continue
        if status != "ok":
            why = "does not exist" if status == "missing" else "is not allowed for this case"
            out.append(_finding(BlockerCode.VER_BAD_CITATION, f"{cid} {why}", stage, cid))
            continue
        sentence = sentence_of(pos)
        claimed = [h for h in find_all(CITE.sub(" ", sentence)) if h.kind != "unparsed"]
        # P11 K2: a figure is grounded by any in-force passage the same sentence cites
        # ("8.51 per cent in May [A], 8.52 per cent in July [B]"); each id is still checked above.
        # A KFS or help passage never lends a figure to a regulation or policy citation
        # (security review K2): it grounds only its own citation.
        same = (
            [cid]
            if cid.startswith(_UNQUOTABLE_IDS)
            else [c for c in CITE.findall(sentence) if not c.startswith(_UNQUOTABLE_IDS)]
        )
        together = " \n".join(
            p for st, p in (found.get(c, ("missing", "")) for c in same) if st == "ok"
        )
        held = find_all(together)
        counted = _counted_words(together)
        for h in claimed:
            if h.kind == "number" and h.value in counted:
                continue
            if not any(p.kind == h.kind and _same(h.kind, p.value, h.value) for p in held):
                out.append(
                    _finding(
                        BlockerCode.VER_BAD_CITATION,
                        f"{cid} does not contain the cited figure",
                        stage,
                        cid,
                    )
                )
                break
    return out


_ONES = {
    w: i
    for i, w in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        ]
    )
}
_TENS = {
    w: 10 * i
    for i, w in enumerate(
        ["_", "_", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    )
    if i >= 2
}
_UNIT = r"(?:working\s+)?(?:days?|weeks?|months?|years?|instalments?)"
_WORDS = "|".join(sorted([*_ONES, *_TENS], key=len, reverse=True))
_COUNT_WORDS = re.compile(
    rf"\b((?:(?:{_WORDS})(?:[\s-]+hundred)?(?:[\s-]+(?:and[\s-]+)?)?)+)\s*{_UNIT}\b", re.I
)


def _cardinal(phrase: str) -> int | None:
    """English cardinal 0-999 ("forty-five", "one hundred and twenty"), or None."""
    total, seen = 0, False
    for w in re.findall(r"[a-z]+", phrase.lower()):
        if w == "and":
            continue
        if w == "hundred":
            if not 0 < total < 10:
                return None
            total *= 100
            continue
        v = _ONES.get(w, _TENS.get(w))
        if v is None:
            return None
        total, seen = total + v, True
    return total if seen else None


def _counted_words(passage: str) -> set[Decimal]:
    """Counts written in words before a period unit ("forty-five days", R-MSME-01 s.15): Acts
    write them out, so a cited "45 days" is checked against them too (P11, VER-02)."""
    out = set()
    for m in _COUNT_WORDS.finditer(passage):
        n = _cardinal(m.group(1))
        if n is not None:
            out.add(Decimal(n))
    return out


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[\w-]+", text.lower()))


def _same(kind: str, a: object, b: object) -> bool:
    if isinstance(a, Decimal) and isinstance(b, Decimal):
        tol = MONEY_TOL if kind == "money" else RATE_TOL if kind == "rate" else Decimal(0)
        return abs(a - b) <= tol
    return a == b


def _sentences_with_offsets(text: str) -> list[tuple[int, str]]:
    out, start = [], 0
    for m in SENTENCE.finditer(text):
        out.append((start, text[start : m.start()]))
        start = m.end()
    out.append((start, text[start:]))
    return out


def verify(
    text: str,
    *,
    facts: Mapping[str, Fact],
    slots: Mapping[str, str] | None = None,
    model: bool = False,
    stage: Stage | None = None,
    resolve: Resolve | None = None,
) -> list[CriticFinding]:
    """Every critical finding for ``text``; an empty list means the Critic passes it."""
    slots = slots or {}
    findings: list[CriticFinding] = []
    if pii.find(text):  # the identifier itself is never echoed into a finding
        findings.append(_finding(BlockerCode.VER_PII, "personal identifier in the text", stage))
        text = pii.redact(text)
    # A citation id is not a figure (same-length blanking keeps offsets). A citing sentence's
    # figures are checked against its passage (VER-02), not the case ledger.
    plain = CITE.sub(lambda m: " " * len(m.group(0)), text)
    sentences = [(a, a + len(s), s) for a, s in _sentences_with_offsets(text) if CITE.search(s)]
    cited = [(a, b) for a, b, _ in sentences]
    ids = list(dict.fromkeys(CITE.findall(text)))
    found = resolve(ids) if resolve is not None and ids else ({} if not ids else None)

    def grounded(start: int, end: int, words: str) -> bool:
        """Inside a citing sentence and, for a flagged word, said by a passage it cites: the word
        with its neighbour on either side ("guaranteed amount", not just "approved")."""
        for a, b, sentence in sentences:
            if not (a <= start and end <= b):
                continue
            held = ((found or {}).get(c, ("missing", "")) for c in CITE.findall(sentence))
            ok = [_norm(p) for status, p in held if status == "ok"]
            if not words:
                return bool(ok)
            before = re.findall(r"[\w-]+", plain[a:start])[-1:]
            after = re.findall(r"[\w-]+", plain[end:b])[:1]
            pairs = [_norm(" ".join([*before, words])), _norm(" ".join([words, *after]))]
            pairs = [x for x in pairs if " " in x]
            return any(x in p for x in pairs for p in ok)
        return False

    findings += _numbers(plain, facts, _spans(plain, slots.values()) + cited, stage, model=model)
    findings += _stale(slots, facts, stage)
    if model:
        findings += _reasons(plain, slots, stage, grounded)

    def authority(start: int, end: int, word: str) -> bool:
        """An approval-matrix word inside a citing sentence that cites only internal policy
        passages, one of which uses the same word, and that names no lender, bank or sanction."""
        for a, b, sentence in sentences:
            if not (a <= start and end <= b):
                continue
            ids = CITE.findall(sentence)
            if not ids or not all(i.startswith(_POLICY_IDS) for i in ids):
                return False
            if _LENDERISH.search(plain[a:b]) or _ADDRESSED.search(plain[a:b]):
                return False  # "approves your proposal" is a prediction (security review K2)
            held = [(found or {}).get(i, ("missing", "")) for i in ids]
            verb = word.lower()
            # P11 K2: "approves" is grounded by the verb "approve" (policy: "shall approve");
            # the noun "approval" never grounds it.
            forms = {"approves", "approve"} if verb == "approves" else {verb}
            return any(
                st == "ok" and forms & set(re.findall(r"[a-z]+", p.lower())) for st, p in held
            )
        return False

    def quoted(start: int, end: int, rule: str) -> bool:
        """P11 K2: the flagged words, with a neighbouring word on each side (two before at the
        sentence end), appear word for word in an in-force public or policy passage the sentence
        cites (four neighbouring words in all). Never for a sentence addressed to the user or
        about the case, proposal or its approvers, and acceptance wording
        never in a sentence about a lender, bank, loan, borrower, offer, agreement or credit."""
        for a, b, sentence in sentences:
            if not (a <= start and end <= b):
                continue
            body = plain[a:b]
            deal = _LENDERISH.search(body) or _DEALISH.search(body)
            if _ADDRESSED.search(body) or _CASEISH.search(body) or (rule == "acceptance" and deal):
                return False
            ids = [i for i in CITE.findall(sentence) if not i.startswith(_UNQUOTABLE_IDS)]
            held = ((found or {}).get(i, ("missing", "")) for i in ids)
            ok = [_norm(p) for st, p in held if st == "ok"]
            words = re.findall(r"[\w-]+", plain[start:end])
            before = re.findall(r"[\w-]+", plain[a:start])
            after = re.findall(r"[\w-]+", plain[end:b])
            # Two neighbouring words on each side; at a sentence edge, more on the other side. Short
            # stock phrases ("is accepted by", "the deadline is") are too common to prove a quote.
            n_after = min(2, len(after))
            n_before = 4 - n_after
            if len(before) < n_before:
                return False
            window = before[len(before) - n_before :] + words + after[:n_after]
            phrase = _norm(" ".join(window))
            return any(f" {phrase} " in f" {p} " for p in ok)
        return False

    # The quote exemption is for copilot answers only (model text, no stage): never narratives or
    # negotiation messages (security review K2).
    findings += _banned(
        plain,
        model=model,
        stage=stage,
        grounded=grounded,
        authority=authority,
        quoted=quoted if model and stage is None else (lambda a, b, r: False),
    )
    findings += _citations(text, found, stage)
    return findings


def report_completeness(report: str, sections: Iterable[str]) -> list[CriticFinding]:
    """VER-04: each required section is a Markdown heading of the report."""
    missing = [
        s
        for s in sections
        if not re.search(rf"^#+\s*{re.escape(s)}\s*$", report, re.MULTILINE | re.IGNORECASE)
    ]
    return [
        _finding(BlockerCode.VER_REPORT_INCOMPLETE, f"missing section: {s}", None) for s in missing
    ]
