"""Span-cited answers (plan v3.4 §7.1 CP-08-lite, P5, scope #64).

Code numbers every sentence of every retrieved passage: span [n.m] is sentence m of passage n.
The model must end each answer sentence with the span ids that support it. `cut` keeps only the
sentences that carry at least one valid span id for this turn (or, on the case-facts path, a
known {slot}); every other sentence is cut. Nothing left means the copilot abstains.

Span ids are assigned by code after the passage text is cleaned, so a document that contains
"[2.3]" cannot forge one: bracketed ids in passage text are removed before numbering.
"""

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

MAX_SPANS = 60  # per passage; a passage is at most a section chunk
_FORGED = re.compile(r"\[\s*\d+\s*\.\s*\d+\s*(?:,\s*\d+\s*\.\s*\d+\s*)*\]")
_SPLIT_SOURCE = re.compile(r"(?<=[.;:!?])\s+(?=[A-Z0-9(\"'₹])|\n+")
_REFS = re.compile(r"\[([^\[\]]*)\]")
_SPAN_ID = re.compile(r"^\s*(\d+)\.(\d+)\s*$")
_SLOT = re.compile(r"\{([\w.\-]+)\}")
# A sentence ends at . ! or ? followed by optional citation brackets, then space + a capital,
# digit, quote or ₹ (so "₹1.5 crore" and "0.85%" never split), or the end of the text.
_SENTENCE_END = re.compile(r"(?<=[.!?])((?:\s*\[[^\[\]]*\])*)\s+(?=[A-Z0-9\"'(₹])")


@dataclass(frozen=True)
class Spanned:
    text: str  # passage text with "[n.m] sentence" lines, for the prompt
    spans: tuple[str, ...]  # sentence m is spans[m - 1]


def number(n: int, section: str, text: str) -> Spanned:
    """Passage n as numbered sentence spans; the section line stays as an unnumbered header."""
    clean = _FORGED.sub(" ", text)
    parts = [p.strip() for p in _SPLIT_SOURCE.split(clean) if p and p.strip()]
    spans = tuple(parts[:MAX_SPANS])
    body = "\n".join(f"[{n}.{m}] {s}" for m, s in enumerate(spans, start=1))
    header = _FORGED.sub(" ", section).strip()
    return Spanned(f"{header}\n{body}" if header else body, spans)


def sentences(answer: str) -> list[str]:
    """Split an answer into sentences, keeping each sentence's trailing citation brackets."""
    out: list[str] = []
    last = 0
    for m in _SENTENCE_END.finditer(answer):
        out.append(answer[last : m.end(1) if m.group(1) else m.start()].strip())
        last = m.end()
    out.append(answer[last:].strip())
    merged: list[str] = []
    for s in (x for x in out if x):
        lead = re.match(r"^((?:\[[^\[\]]*\]\s*)+)(.*)$", s, re.S)
        if lead and merged:  # "… amount. [1.2] Next …": the ids belong to the sentence before
            merged[-1] = f"{merged[-1]} {lead.group(1).strip()}"
            s = lead.group(2).strip()
            if not s:
                continue
        merged.append(s)
    return merged


@dataclass(frozen=True)
class Cut:
    text: str  # kept sentences, span ids replaced by [chunk_id]
    kept: int
    cut: int
    cited: tuple[int, ...]  # passage numbers in order of first citation
    span_ids: tuple[str, ...]  # "n.m" in order of first citation
    slots: tuple[str, ...]  # slot keys used in kept sentences


def cut(
    answer: str,
    spans: Mapping[int, Sequence[str]],
    source_map: Mapping[int, str],
    slot_keys: Collection[str],
) -> Cut:
    """Keep sentences with ≥1 valid span id (or a known slot and no invalid id); cut the rest.
    A sentence citing any id that is not a span of this turn is cut whole."""
    kept: list[str] = []
    cited: list[int] = []
    span_ids: list[str] = []
    used_slots: list[str] = []
    dropped = 0
    for sentence in sentences(answer):
        ids: list[tuple[int, int]] = []
        invalid = False
        for group in _REFS.findall(sentence):
            for token in group.split(","):
                m = _SPAN_ID.match(token)
                n, k = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
                if not m or n not in source_map or not 1 <= k <= len(spans.get(n, ())):
                    invalid = True
                    continue
                ids.append((n, k))
        slots = _SLOT.findall(sentence)
        bad_slot = any(s not in slot_keys for s in slots)
        if invalid or bad_slot or not (ids or slots):
            dropped += 1
            continue

        def to_chunks(m: re.Match[str]) -> str:
            seen: list[str] = []
            for token in m.group(1).split(","):
                g = _SPAN_ID.match(token)
                if g and source_map[int(g.group(1))] not in seen:
                    seen.append(source_map[int(g.group(1))])
            return "".join(f"[{c}]" for c in seen)

        kept.append(_REFS.sub(to_chunks, sentence))
        for n, k in ids:
            if n not in cited:
                cited.append(n)
            if f"{n}.{k}" not in span_ids:
                span_ids.append(f"{n}.{k}")
        used_slots.extend(s for s in slots if s not in used_slots)
    return Cut(
        " ".join(kept),
        len(kept),
        dropped,
        tuple(cited),
        tuple(span_ids),
        tuple(used_slots),
    )
