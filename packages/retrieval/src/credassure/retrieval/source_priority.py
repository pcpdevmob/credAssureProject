"""Source priority (P11, SOURCE_PRIORITY): the order of the passages the copilot reads.

Retrieval already chose the k passages; this only reorders them, by the kind of source, keeping the
retrieval order inside each tier (a stable sort). Nothing is added or removed, so recall@k and the
answerability gate are unchanged.

  tier 0 primary instruments: Acts, Rules, Regulations, Directions, notifications, scheme
         documents, the team's own policies, a case's KFS
  tier 1 explanations from an issuing body: FAQs, circulars, guidelines, everything else
  tier 2 secondary accounts: parliamentary answers, court judgments

Why: on the G4 live run (2026-11-19) the copilot's answers were right and Critic-checked, but cited
a parliamentary answer or an FAQ that restated an Act or a policy also in its top five; the model
tends to cite the passage it reads first. The rule is generic (document kind only), chosen before
measuring, and kept only if the retrieval dev split improves (scripts/copilot_dev_citations.py).
"""

import re
from collections.abc import Sequence
from typing import Any, Protocol

_PRIMARY = re.compile(
    r"\b(?:act|rules|regulations|directions?|master direction|notification|scheme document)\b",
    re.IGNORECASE,
)
_FAQ = re.compile(r"\bfaqs?\b|frequently asked", re.IGNORECASE)
_PARLIAMENT = re.compile(r"\b(?:lok sabha|rajya sabha|starred q|unstarred q)", re.IGNORECASE)


class _Source(Protocol):
    doc_id: str
    title: str
    collection: str


def tier(p: _Source | dict[str, Any]) -> int:
    """0 primary instrument, 1 explanation, 2 secondary account (id, title, collection only)."""
    row = p if isinstance(p, dict) else vars(p)
    doc_id, title = str(row["doc_id"]), str(row.get("title") or "")
    collection = str(row.get("collection"))
    if doc_id.startswith(("R-SANSAD-", "R-JUD-")) or _PARLIAMENT.search(title):
        return 2
    if collection == "kfs":
        return 0
    if collection == "policy":
        return 1 if doc_id.startswith("FAQ-") or _FAQ.search(title) else 0
    if _FAQ.search(title):
        return 1
    return 0 if _PRIMARY.search(title) else 1


def prioritise[T](passages: Sequence[T]) -> list[T]:
    """The same passages, primary instruments first; retrieval order kept within a tier."""
    return sorted(passages, key=tier)  # type: ignore[arg-type]
