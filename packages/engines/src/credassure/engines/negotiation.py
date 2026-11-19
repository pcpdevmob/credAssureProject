"""Negotiation moves: choose each round's target and the verified figure it cites (LW-12/13/15,
BR-09/10, ADR 0037). Pure.

Round 1, fee waiver: the comparable offer with the highest processing fee in rupees (fee x
principal for a percentage fee, ADR 0021) asks for a waiver citing the lowest such fee among the
other comparable offers. Fewer than two comparable offers: no fee-waiver move.
Rounds 2-3 (``MOVES`` order, each move at most once, a move with no target is skipped): rate
match and tenor change, below.
A concession counts only when the received revision re-audits as comparable and is better on the
term the move asked about.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from typing import Any

from credassure.core.blockers import BlockerCode
from credassure.core.money import MONEY

from .calendar import add_months, week_of, week_start
from .loancost import dec

PROCESSING_FEE = "Processing fee"


def processing_fee(offer: Mapping[str, Any]) -> Decimal:
    """The processing fee as stated (fraction or ₹, per its basis)."""
    fee = next((f for f in offer.get("fees", []) if f["name"] == PROCESSING_FEE), None)
    return Decimal(0) if fee is None else dec(fee["value"])


def fee_rupees(offer: Mapping[str, Any]) -> Decimal:
    """The processing fee in ₹, so fixed and percentage fees compare like with like."""
    fee = next((f for f in offer.get("fees", []) if f["name"] == PROCESSING_FEE), None)
    if fee is None:
        return Decimal(0)
    with localcontext(MONEY):
        value = dec(fee["value"])
        return value * dec(offer["principal"]) if fee["basis"] == "pct_of_principal" else value


@dataclass(frozen=True)
class Plan:
    target_offer: str
    lender_id: str
    current_fee: Decimal
    competing_fee: Decimal
    competing_offer: str = ""
    current_basis: str = "pct_of_principal"
    competing_basis: str = "pct_of_principal"


def plan(comparable: Sequence[Mapping[str, Any]]) -> Plan | None:
    if len(comparable) < 2:
        return None
    target = max(comparable, key=fee_rupees)
    competitor = min((o for o in comparable if o is not target), key=fee_rupees)
    return Plan(
        str(target["offer_id"]),
        str(target["lender_id"]),
        processing_fee(target),
        processing_fee(competitor),
        str(competitor["offer_id"]),
        _basis(target),
        _basis(competitor),
    )


def _basis(offer: Mapping[str, Any]) -> str:
    fee = next((f for f in offer.get("fees", []) if f["name"] == PROCESSING_FEE), None)
    return "pct_of_principal" if fee is None else str(fee["basis"])


def concession_counts(
    original: Mapping[str, Any], revised: Mapping[str, Any] | None, revised_comparable: bool
) -> bool:
    return revised is not None and revised_comparable and fee_rupees(revised) < fee_rupees(original)


# ---- rounds 2-3 (LW-15, ADR 0037): rate match and tenor change ----------------------------------
FEE_WAIVER, RATE_MATCH, TENOR_CHANGE = "fee_waiver_v1", "rate_match_v1", "tenor_change_v1"
MOVES = (FEE_WAIVER, RATE_MATCH, TENOR_CHANGE)  # fixed order; each move at most once per case
MAX_ROUNDS = 3  # LW-15: three rounds maximum
MAX_EXTRA_MONTHS = 6  # a tenor-change request never asks for a longer moratorium than this


@dataclass(frozen=True)
class Standing:
    """An offer at its latest version, as the last comparison left it (ledger facts)."""

    offer: Mapping[str, Any]
    comparable: bool
    eligible: bool  # comparable, affordable, on time and enough (LW-09/10)
    rank: int | None
    apr: Decimal | None
    flags: frozenset[str]


@dataclass(frozen=True)
class RateMatch:
    target_offer: str
    lender_id: str
    current_rate: Decimal
    competing_rate: Decimal
    competing_offer: str


@dataclass(frozen=True)
class TenorChange:
    target_offer: str
    lender_id: str
    current_first: date
    requested_first: date
    extra_months: int
    cash_low_week_start: date


def _rate(s: Standing) -> Decimal:
    return dec(s.offer["annual_rate"])


def rate_match(standings: Sequence[Standing]) -> RateMatch | None:
    """Ask the best-ranked fixed-rate eligible offer whose annual rate is above the lowest annual
    rate among the other eligible offers to match it, citing that offer. Fewer than two eligible
    offers, or none dearer than its competitors: no move. A floating rate resets: never a target."""
    eligible = [s for s in standings if s.eligible]
    if len(eligible) < 2:
        return None
    fixed = [s for s in eligible if s.offer.get("rate_type") == "fixed"]
    for target in sorted(fixed, key=lambda s: (s.rank or 10**6, str(s.offer["offer_id"]))):
        best = min(
            (s for s in eligible if s is not target),
            key=lambda s: (_rate(s), str(s.offer["offer_id"])),
        )
        if _rate(target) > _rate(best):
            return RateMatch(
                str(target.offer["offer_id"]),
                str(target.offer["lender_id"]),
                _rate(target),
                _rate(best),
                str(best.offer["offer_id"]),
            )
    return None


def first_due(offer: Mapping[str, Any], extra_months: int = 0) -> date:
    disbursal = date.fromisoformat(str(offer["disbursal_date"]))
    return add_months(disbursal, int(offer.get("moratorium_months", 0)) + extra_months + 1)


def tenor_change(standings: Sequence[Standing], week1: date, peak_week: int) -> TenorChange | None:
    """Ask the cheapest comparable offer that is unaffordable (LW-09) for a longer moratorium, so
    its first repayment falls after the cash low point (the peak-shortfall week), the tenure
    extended by the same months so the instalment is unchanged. An offer that already starts
    repaying after the low point, or would need more than ``MAX_EXTRA_MONTHS``: no move."""
    unaffordable = [
        s for s in standings if s.comparable and BlockerCode.LW_NOT_AFFORDABLE.value in s.flags
    ]
    low = week_start(peak_week, week1)
    for s in sorted(unaffordable, key=lambda s: (s.apr is None, s.apr, str(s.offer["offer_id"]))):
        if week_of(first_due(s.offer), week1) > peak_week:
            continue  # a later start would not move it past the low point
        for extra in range(1, MAX_EXTRA_MONTHS + 1):
            if week_of(first_due(s.offer, extra), week1) > peak_week:
                return TenorChange(
                    str(s.offer["offer_id"]),
                    str(s.offer["lender_id"]),
                    first_due(s.offer),
                    first_due(s.offer, extra),
                    extra,
                    low,
                )
    return None


def rate_counts(
    original: Mapping[str, Any], revised: Mapping[str, Any] | None, revised_comparable: bool
) -> bool:
    return (
        revised is not None
        and revised_comparable
        and dec(revised["annual_rate"]) < dec(original["annual_rate"])
    )


def tenor_counts(
    original: Mapping[str, Any], revised: Mapping[str, Any] | None, revised_comparable: bool
) -> bool:
    return (
        revised is not None
        and revised_comparable
        and int(revised.get("moratorium_months", 0)) > int(original.get("moratorium_months", 0))
    )
