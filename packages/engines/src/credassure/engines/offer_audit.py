"""Offer audit (LW-02/03/04/08, BR-06, ADR 0021). Pure.

Comparable = every material term present, stated instalment within ₹1 of the recomputed one,
and the first repayment date consistent with the disbursal and moratorium. Hidden charges come
from the caller (the LendWise agent reads the KFS schedule; code checks it); they are flagged here
and priced by ``loancost``. Benchmark and guarantee findings are warnings, not gates.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, localcontext
from typing import Any

from credassure.core.blockers import BlockerCode
from credassure.core.money import MONEY

from .calendar import add_months
from .loancost import Charge, dec, instalment

MATERIAL_TERMS = (
    "principal",
    "annual_rate",
    "tenure_months",
    "fees",
    "repayment",
    "disbursal_date",
    "first_repayment_date",
    "rate_type",
)
INSTALMENT_TOLERANCE = Decimal(1)


@dataclass(frozen=True)
class Audit:
    offer_id: str
    comparable: bool
    flags: tuple[str, ...]
    missing_terms: tuple[str, ...] = field(default=())


def audit(offer: Mapping[str, Any], hidden: Sequence[Charge], enterprise_class: str) -> Audit:
    missing = tuple(t for t in MATERIAL_TERMS if t not in offer)
    if missing:
        missing_flags = tuple(f"{BlockerCode.LW_MISSING_MATERIAL_TERM}:{t}" for t in missing)
        return Audit(str(offer["offer_id"]), False, missing_flags, missing)
    flags: list[str] = []
    disbursal = date.fromisoformat(str(offer["disbursal_date"]))
    first_due = add_months(disbursal, int(offer.get("moratorium_months", 0)) + 1)
    if date.fromisoformat(str(offer["first_repayment_date"])) != first_due:
        flags.append(BlockerCode.LW_SCHEDULE_DATE_MISMATCH)
    stated = offer.get("stated_instalment")
    with localcontext(MONEY):
        if stated is not None and abs(dec(stated) - instalment(offer)) > INSTALMENT_TOLERANCE:
            flags.append(BlockerCode.LW_INSTALMENT_MISMATCH)
    flags += [f"{BlockerCode.LW_HIDDEN_CHARGE}:{h.name}" for h in hidden]
    if offer["rate_type"] == "floating":
        flags.append(BlockerCode.LW_RATE_MAY_RESET)
        if offer.get("benchmark") != "EBLR" and enterprise_class in {"micro", "small"}:
            flags.append(BlockerCode.LW_BENCHMARK_NOT_EXTERNAL)
    if offer.get("guarantee") and enterprise_class == "medium":
        flags.append(BlockerCode.LW_CGTMSE_INELIGIBLE)
    blocking = {BlockerCode.LW_INSTALMENT_MISMATCH, BlockerCode.LW_SCHEDULE_DATE_MISMATCH}
    return Audit(str(offer["offer_id"]), not blocking & set(flags), tuple(str(f) for f in flags))
