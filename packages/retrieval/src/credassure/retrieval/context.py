"""Contextual chunk headers (plan v3.4 §7.1, scope #61, KR-01/KR-03).

A deterministic header, "publisher · title · section · effective date", is prepended to each
**section** chunk before it is embedded. The stored chunk text, its chunk_id and its position never
change, so every citation already given still resolves (the chunk_id stability test). Keyword
search and the citation endpoint read the stored text, unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .sources import SourceDoc

CONTEXT_VERSION = "ctx1"  # part of the index version when headers are on: a toggle re-indexes
HEADED_STRATEGIES = frozenset({"section"})


def header(doc: SourceDoc, section_path: str | None) -> str:
    parts = [
        doc.publisher or "",
        doc.title,
        section_path or "",
        doc.effective_from.isoformat() if doc.effective_from else "",
    ]
    return " · ".join(p.strip() for p in parts if p and p.strip())


def embed_text(doc: SourceDoc, strategy: str, text: str, path: str | None, *, on: bool) -> str:
    """What the embedder sees for one chunk."""
    if not on or strategy not in HEADED_STRATEGIES:
        return text
    return f"{header(doc, path)}\n\n{text}"
