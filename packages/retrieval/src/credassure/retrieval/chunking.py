"""KR-01: three ways to split a document into passages.

Every chunk carries the section it sits in (`section_path`, e.g. "Chapter VIII > 348. Key Facts
Statement"), so labels written against document + section survive re-chunking (DATA_SPEC §7).

Bump CHUNKER_VERSION whenever output changes: ingest re-chunks every document whose version differs.
"""

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

CHUNKER_VERSION = "3"
STRATEGIES = ("fixed512", "section", "semantic")
SIZE, OVERLAP, UNIT = 512, 64, 64

Embed = Callable[[list[str]], list[list[float]]]


@dataclass(frozen=True)
class Piece:
    text: str
    section_path: str | None


_RUNNING_HEADER = re.compile(r"gazet+e of india", re.IGNORECASE)  # page headers in Gazette PDFs
_MD = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
_NUMBERED = re.compile(r"^(\d{1,3}(?:\.\d{1,3})*)\.?\s+[A-Z(\"“]")
# "Chapter III - Benchmark", "PART II", "Annex", "Schedule." but not "part of the establishment".
_KEYWORD = re.compile(
    r"^(chapter|part|annex(ure)?|schedule|appendix)([\s.:-]*$|\s+([ivxlc]+|\d+|[a-z])\b)",
    re.IGNORECASE,
)


def _heading(line: str) -> int | None:
    """Heading level or None: Chapter/Annex/ALL CAPS = 1; "1." = 2; "1.1" = 3; "#" = count."""
    if m := _MD.match(line):
        return len(m.group(1))
    if len(line) > 120 or len(line.split()) > 12 or _RUNNING_HEADER.search(line):
        return None
    if m := _NUMBERED.match(line):
        return 1 + m.group(1).count(".") + 1
    if _KEYWORD.match(line):
        return 1
    letters = [c for c in line if c.isalpha()]
    caps = line.isascii() and len(letters) >= 4 and all(c.isupper() for c in letters)
    if caps and (len(line.split()) >= 2 or len(letters) >= 9):  # not lone codes like "KLEMS"
        return 1
    return None


def sections(text: str) -> list[tuple[str | None, str]]:
    """(section_path, body) blocks in order. The heading title starts its body (no "#" markers)."""
    stack: list[tuple[int, str]] = []
    blocks: list[tuple[str | None, list[str]]] = [(None, [])]
    for raw in text.splitlines():
        line = raw.strip()
        level = _heading(line) if line else None
        if level is None:
            if line:
                blocks[-1][1].append(line)
            continue
        title = m.group(2) if (m := _MD.match(line)) else line
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        blocks.append((" > ".join(t for _, t in stack), [title]))
    return [(path, "\n".join(lines)) for path, lines in blocks if lines]


_TOKEN = re.compile(r"\S+\s*")


def _tokens(body: str) -> list[str]:
    """Words with their trailing whitespace, so a chunk keeps its line breaks (the injection
    scanner's line-anchored rules and readable passages both need them)."""
    return _TOKEN.findall(body)


def _join(tokens: list[str]) -> str:
    return "".join(tokens).strip()


def _windows(n: int, size: int, overlap: int) -> list[tuple[int, int]]:
    out, step = [], max(1, size - overlap)
    for start in range(0, n, step):
        out.append((start, min(n, start + size)))
        if start + size >= n:
            break
    return out


def _words(text: str) -> tuple[list[str], list[str | None]]:
    words: list[str] = []
    labels: list[str | None] = []
    for path, body in sections(text):
        w = _tokens(body)
        words += w
        labels += [path] * len(w)
    return words, labels


def fixed(text: str, size: int = SIZE, overlap: int = OVERLAP) -> list[Piece]:
    # ponytail: tokens = whitespace words (~1.3 model tokens each); add a tokenizer if size matters.
    words, labels = _words(text)
    return [Piece(_join(words[a:b]), labels[a]) for a, b in _windows(len(words), size, overlap)]


def by_section(text: str, size: int = SIZE) -> list[Piece]:
    out = []
    for path, body in sections(text):
        words = _tokens(body)
        out += [Piece(_join(words[a:b]), path) for a, b in _windows(len(words), size, OVERLAP)]
    return out


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / (na * nb) if na and nb else 0.0


def semantic(text: str, embed: Embed, unit: int = UNIT, size: int = SIZE) -> list[Piece]:
    """Split where neighbouring spans are least alike (bottom quartile) or at `size` words."""
    units: list[tuple[str | None, list[str]]] = []
    for path, body in sections(text):
        words = _tokens(body)
        units += [(path, words[a:b]) for a, b in _windows(len(words), unit, 0)]
    if not units:
        return []
    vectors = embed([_join(w) for _, w in units])
    sims = [_cosine(vectors[i], vectors[i + 1]) for i in range(len(units) - 1)]
    cut = sorted(sims)[len(sims) // 4] if sims else 0.0
    out: list[Piece] = []
    path, current = units[0][0], list(units[0][1])
    for i in range(1, len(units)):
        nxt_path, nxt = units[i]
        if sims[i - 1] < cut or len(current) + len(nxt) > size:
            out.append(Piece(_join(current), path))
            path, current = nxt_path, []
        current += nxt
    out.append(Piece(_join(current), path))
    return out
