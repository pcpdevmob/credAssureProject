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


def _banned(
    text: str,
    *,
    model: bool,
    stage: Stage | None,
    grounded: Callable[[int, int, str], bool] = lambda a, b, w: False,
) -> list[CriticFinding]:
    b = banned()
    rules = list(b.all)
    if model and stage is not None:
        rules += b.model_only.get(stage.value, ())

    def excused(m: re.Match[str]) -> bool:
        # Only a quoted noun term ("guaranteed amount") is excused, never a prediction or
        # acceptance phrase, however common its word pair is in passages (9e security review).
        term = _TERMS.match(text, m.start())
        return term is not None and grounded(m.start(), term.end(), term[0])

    out = []
    for name, rx in rules:
        m = next((m for m in rx.finditer(text) if not excused(m)), None)
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
    for cid, pos in cited:
        status, passage = found.get(cid, ("missing", ""))
        if status == "superseded":
            out.append(
                _finding(BlockerCode.VER_SUPERSEDED_SOURCE, f"{cid} is not in force", stage, cid)
            )
            continue
        if status != "ok":
            why = "does not exist" if status == "missing" else "is not allowed for this case"
            out.append(_finding(BlockerCode.VER_BAD_CITATION, f"{cid} {why}", stage, cid))
            continue
        sentence = next(s for s in _sentences_with_offsets(text) if s[0] <= pos < s[0] + len(s[1]))[
            1
        ]
        claimed = [h for h in find_all(CITE.sub(" ", sentence)) if h.kind != "unparsed"]
        held = find_all(passage)
        for h in claimed:
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
    findings += _banned(plain, model=model, stage=stage, grounded=grounded)
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
