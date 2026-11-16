"""Repayment fit and timing (LW-09/10, BR-07, ADR 0021). Pure, Decimal.

For every week of the cash table: cumulative cash + undrawn limits + mitigations + the amount
received (from the disbursal week) - every borrower payment so far must stay >= the minimum
buffer. Payment k falls on disbursal + k calendar months (ADR 0011). Late = disbursal after the
peak-shortfall week; short = principal below the recommended amount.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext

from credassure.core.money import MONEY

from .calendar import add_months, week_of


@dataclass(frozen=True)
class Fit:
    lowest_cash: Decimal
    affordable: bool
    late: bool
    short: bool
    breach_week: int | None = None  # first week cash < buffer (the "unaffordable in week N" reason)


def assess(
    cumulative: Sequence[Decimal],
    available: Decimal,
    buffer: Decimal,
    flows: Sequence[Decimal],
    disbursal: date,
    week1: date,
    principal: Decimal,
    need: Decimal,
    peak_week: int,
) -> Fit:
    weeks = len(cumulative)
    with localcontext(MONEY):
        payments = [Decimal(0)] * (weeks + 1)
        for k in range(1, len(flows)):
            week = week_of(add_months(disbursal, k), week1)
            if 1 <= week <= weeks:
                payments[week] -= flows[k]
        received_week = week_of(disbursal, week1)
        lowest, paid, breach = None, Decimal(0), None
        for week in range(1, weeks + 1):
            paid += payments[week]
            received = flows[0] if week >= received_week else Decimal(0)
            cash = cumulative[week - 1] + available + received - paid
            lowest = cash if lowest is None or cash < lowest else lowest
            if breach is None and week >= received_week and cash < buffer:  # repayments' week
                breach = week
    if lowest is None:
        raise ValueError("the cash table has no weeks")
    return Fit(lowest, lowest >= buffer, received_week > peak_week, principal < need, breach)
