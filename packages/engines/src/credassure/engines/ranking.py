"""Offer ranking and the lender-comparison gate (LW-11, LW-14, BR-06/07, ADR 0021). Pure.

Eligible = comparable, affordable and neither late nor short. Rank by APR, then total cost,
then disbursal date. GO needs at least two eligible offers; NOT_REQUIRED when the need is ₹0.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

Gate = Literal["GO", "NO_GO", "NOT_REQUIRED"]


@dataclass(frozen=True)
class Candidate:
    offer_id: str
    eligible: bool
    apr: Decimal
    total_cost: Decimal
    disbursal: date


@dataclass(frozen=True)
class Ranking:
    gate: Gate
    order: tuple[str, ...]


def rank(candidates: Sequence[Candidate], need: Decimal) -> Ranking:
    if need == 0:
        return Ranking("NOT_REQUIRED", ())
    eligible = sorted(
        (c for c in candidates if c.eligible),
        # LW-11 ties at the displayed precision (0.01 pp) go to total cost, as in gold
        key=lambda c: (
            (c.apr * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            c.total_cost,
            c.disbursal,
            c.offer_id,
        ),
    )
    order = tuple(c.offer_id for c in eligible)
    return Ranking("GO" if len(order) >= 2 else "NO_GO", order)
