"""Excerpt cap for cited passages (UI-06, ADR 0029 rail R2; moved from the citations router).

Only legal bases L1 (open data), L2 (Gazette matter) and L5 (team-owned) are shown in full. Every
other basis, L3 and L4 included, and an unknown or missing one, is limited to a 600 character
excerpt (fail closed). The values come from `config/guardrails.yaml`.
"""

from .policy import load

FULL_TEXT_BASES = load().full_text_bases  # anything else is capped: fail closed
EXCERPT_LIMIT = load().excerpt_limit  # characters of a capped passage that may be shown


def excerpt(text: str, quote: str | None, limit: int = EXCERPT_LIMIT) -> str:
    """At most ``limit`` characters, centred on the longest word of ``quote`` found in the text
    (else the start). A window, not a summary: the characters are the source's own."""
    if len(text) <= limit:
        return text
    centre, lowered = 0, text.lower()
    words = {w for w in (quote or "").lower().split() if len(w) >= 4}
    for word in sorted(words, key=len, reverse=True):
        at = lowered.find(word)
        if at >= 0:
            centre = at + len(word) // 2
            break
    start = max(0, min(centre - limit // 2, len(text) - limit))
    return text[start : start + limit]
