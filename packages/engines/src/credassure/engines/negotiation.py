"""Fee-waiver round 1: choose the target and the verified competing fee (LW-12/13, BR-09/10). Pure.

The comparable offer with the highest processing fee asks for a waiver citing the lowest
processing fee among the other comparable offers. Fewer than two comparable offers: no round.
A concession counts only when the received revision re-audits as comparable and is cheaper.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Any

from credassure.core.money import MONEY

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
    )


def concession_counts(
    original: Mapping[str, Any], revised: Mapping[str, Any] | None, revised_comparable: bool
) -> bool:
    return revised is not None and revised_comparable and fee_rupees(revised) < fee_rupees(original)
