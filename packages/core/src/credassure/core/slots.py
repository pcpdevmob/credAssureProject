"""Slot-based narratives (BR-05, WC-07, ONB-04; the Verification Critic checks the result).

The model writes ``{key}`` placeholders, never a figure or a comparison. Code owns every value and
every direction word: amounts, rates, dates, weeks and words such as "lower than" are rendered here.
A draft with an unknown slot, a missing required slot, or any figure outside a slot (a digit, ₹, %,
a number word, a link) is rejected, and the caller uses its template.
"""

import re
from collections.abc import Iterable, Mapping
from datetime import date
from decimal import Decimal

from credassure.core.money import format_inr

SLOT = re.compile(r"\{([A-Za-z0-9_.\-]+)\}")
# Anything that can carry a figure the code did not render.
_FIGURES = re.compile(
    r"\d|₹|%|\bRs\b|[{}]|https?://|www\."
    r"|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty"
    r"|fifty|hundred|thousand|lakh|lac|crore|cr|percent|half|quarter|double|twice)s?\b",
    re.IGNORECASE,
)
# Comparisons and directions are computed in code and passed as slot words (9b: one draft said
# "higher than the request" when it was lower).
_DIRECTIONS = re.compile(
    r"\b(?:higher|lower|greater|smaller|larger|more|less|fewer|exceed\w*|cheap\w*|expensive"
    r"|dear\w*|costl\w*|affordabl\w*|unaffordabl\w*|before|after|earlier|later|above|under)\b",
    re.IGNORECASE,
)
_REPEAT = re.compile(r"\b(\w+)\s+\1\b")  # case-sensitive: "of OF-01-A" is no repeat


def money(amount: Decimal) -> str:
    return format_inr(amount)


def rate(fraction: Decimal) -> str:
    """0.1756 -> '17.56%' (two decimals, the 0.01 pp display precision)."""
    return f"{(fraction * 100).quantize(Decimal('0.01'))}%"


def day(value: date) -> str:
    return value.strftime("%d %b %Y")


def compare(a: Decimal, b: Decimal, lower: str = "lower than", higher: str = "higher than") -> str:
    """Direction word for ``a`` against ``b``, decided in code."""
    return lower if a < b else higher if a > b else "equal to"


def render(
    draft: str,
    slots: Mapping[str, str],
    *,
    required: Iterable[str] = (),
    forbidden: Iterable[str] = (),
    banned: re.Pattern[str] | None = None,
) -> str | None:
    """The rendered text, or None when the draft must be replaced by the template."""
    used = SLOT.findall(draft)
    if not used or any(key not in slots for key in used):
        return None
    if any(key not in used for key in required) or any(key in used for key in forbidden):
        return None
    rest = SLOT.sub(" ", draft)
    rendered = SLOT.sub(lambda m: slots[m.group(1)], draft).strip()
    if _REPEAT.search(rendered):  # "10 weeks weeks": the model wrapped a slot in its own words
        return None
    if (
        _FIGURES.search(rest)
        or _DIRECTIONS.search(rest)
        or (banned is not None and banned.search(rest))
    ):
        return None
    return rendered
