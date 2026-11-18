"""Product help as a citable source for Ask CredAssure (ADR 0035, CP-07/CP-10 scope).

`docs/help/*.md` is team-written (legal basis L5) and small, so it is indexed in memory at gateway
start: one passage per `##`/`###` section, id ``HELP-<page>#<slug>``, scored with BM25 over plain
word tokens. No embeddings, no corpus.db write, no re-ingest. The ids resolve for the Critic
(VER-02) through :meth:`HelpIndex.resolve`, exactly as corpus chunk ids do.

The anchor matches the web help centre (`/help/#<page>`), so a citation opens the page it came from.
"""

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

COLLECTION = "help"
PREFIX = "HELP-"
_HEADING = re.compile(r"^(#{1,3})\s+(.*\S)\s*$", re.MULTILINE)
_QUESTION = re.compile(r"^\*\*(.+?)\*\*\s*$", re.MULTILINE)
_WORD = re.compile(r"[a-z0-9₹]+")
_STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "can",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "if",
        "in",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "so",
        "the",
        "this",
        "to",
        "was",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "you",
        "your",
    ]
)
K1, B = 1.2, 0.75  # BM25 defaults
MAX_PASSAGE = 1800  # characters; a help section is short, this only caps a pathological file


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if t not in _STOP]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "section"


@dataclass(frozen=True)
class HelpPassage:
    chunk_id: str  # HELP-<page>#<slug>
    doc_id: str  # HELP-<page>
    page: str
    title: str  # the page title
    section_path: str  # the section heading
    text: str

    def as_passage(self) -> dict[str, Any]:
        """The shape the copilot gets from every search tool."""
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "section_path": self.section_path,
            "effective_from": None,
            "collection": COLLECTION,
            "text": self.text,
            "injection_flag": False,  # the copilot still scans every passage itself (BR-15)
            "href": f"/help/#{self.page}",
        }


def parse(page: str, source: str) -> list[HelpPassage]:
    """Split one help page into its sections. Text before the first `##` is the page intro."""
    m = re.search(r"^#\s+(.*\S)\s*$", source, re.MULTILINE)
    title = m.group(1) if m else page
    heads = [h for h in _HEADING.finditer(source) if len(h.group(1)) >= 2]
    bounds = [(h.start(), h.end(), h.group(2)) for h in heads]
    if not bounds:  # a FAQ: each bold question line starts a section
        bounds = [(q.start(), q.end(), q.group(1)) for q in _QUESTION.finditer(source)]
    out: list[HelpPassage] = []
    intro_end = bounds[0][0] if bounds else len(source)
    intro = source[m.end() if m else 0 : intro_end].strip()
    if intro:
        out.append(_passage(page, title, "Overview", intro))
    for i, (_, end, head) in enumerate(bounds):
        stop = bounds[i + 1][0] if i + 1 < len(bounds) else len(source)
        body = source[end:stop].strip()
        if body:
            out.append(_passage(page, title, head, body))
    seen: Counter[str] = Counter()
    unique = []
    for p in out:  # two sections with the same heading keep distinct ids
        seen[p.chunk_id] += 1
        cid = p.chunk_id if seen[p.chunk_id] == 1 else f"{p.chunk_id}-{seen[p.chunk_id]}"
        unique.append(HelpPassage(cid, p.doc_id, p.page, p.title, p.section_path, p.text))
    return unique


def _passage(page: str, title: str, head: str, body: str) -> HelpPassage:
    return HelpPassage(
        f"{PREFIX}{page}#{slug(head)}", f"{PREFIX}{page}", page, title, head, body[:MAX_PASSAGE]
    )


class HelpIndex:
    """BM25 over help sections. Immutable after construction; safe to share across requests."""

    def __init__(self, passages: Iterable[HelpPassage]) -> None:
        self.passages = tuple(passages)
        self._by_id = {p.chunk_id: p for p in self.passages}
        self._docs = [
            Counter(_tokens(f"{p.title} {p.section_path} {p.text}")) for p in self.passages
        ]
        self._len = [sum(d.values()) for d in self._docs]
        self._avg = (sum(self._len) / len(self._len)) if self._len else 0.0
        df: Counter[str] = Counter()
        for d in self._docs:
            df.update(d.keys())
        n = len(self._docs)
        self._idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    @classmethod
    def load(cls, directory: Path) -> "HelpIndex":
        """Every `*.md` in ``directory``; none (or no directory) gives an empty index, so help
        questions abstain."""
        if not directory.is_dir():
            return cls(())
        out: list[HelpPassage] = []
        for f in sorted(directory.glob("*.md")):
            out += parse(f.stem, f.read_text(encoding="utf-8"))
        return cls(out)

    def __len__(self) -> int:
        return len(self.passages)

    def search(self, query: str, k: int = 5) -> list[dict[str, Any]]:
        """The top ``k`` sections with a positive score, best first."""
        terms = set(_tokens(query))
        scored = []
        for i, d in enumerate(self._docs):
            s = 0.0
            for t in terms:
                f = d.get(t, 0)
                if f:
                    norm = K1 * (1 - B + B * self._len[i] / (self._avg or 1))
                    s += self._idf[t] * f * (K1 + 1) / (f + norm)
            if s > 0:
                scored.append((s, i))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [self.passages[i].as_passage() for _, i in scored[:k]]

    def resolve(self, ids: Sequence[str]) -> Mapping[str, tuple[str, str]]:
        """VER-02: ``{id: ("ok", text)}`` for known ids, ``("missing", "")`` otherwise."""
        return {
            i: ("ok", self._by_id[i].text) if i in self._by_id else ("missing", "") for i in ids
        }

    def get(self, chunk_id: str) -> HelpPassage | None:
        return self._by_id.get(chunk_id)
