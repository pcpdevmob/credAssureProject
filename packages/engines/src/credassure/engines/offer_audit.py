"""Offer audit (LW-01/02/03/04/08, BR-06, ADR 0021). Pure.

Comparable = every material term present and priceable, stated instalment within ₹1 of the
recomputed one, and the first repayment date consistent with the disbursal and moratorium. Hidden charges come
from the caller (the LendWise agent reads the KFS schedule; code checks it); they are flagged here
and priced by ``loancost``. Benchmark and guarantee findings are warnings, not gates.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, localcontext
from typing import Any

from credassure.core.blockers import BlockerCode
from credassure.core.money import MONEY

from .calendar import add_months
from .loancost import CGTMSE_BASIS, Charge, dec, instalment
from .normaliser import find_all

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
MAX_TENURE_MONTHS = 360  # 30 years; a working-capital term loan is far shorter
_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(upfront|monthly|annual)\s*\|\s*([^|]+?)\s*\|$")
_UNTAXED = re.compile(r"\b(gst[ -]exempt|exempt from gst|no gst|without gst|gst nil)\b", re.I)


@dataclass(frozen=True)
class Audit:
    offer_id: str
    comparable: bool
    flags: tuple[str, ...]
    missing_terms: tuple[str, ...] = field(default=())
    invalid_terms: tuple[str, ...] = field(default=())


def _number(value: Any) -> Decimal | None:
    try:
        number = dec(value)
    except (ArithmeticError, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def invalid_terms(offer: Mapping[str, Any]) -> tuple[str, ...]:
    """Terms of a complete offer that cannot be priced (LW-01, fail closed): a value no loan has
    (a typing slip such as 12.5 for 12.5%, a zero rate, no repayment month left) or a term ADR 0021
    leaves unpriced (financed insurance, a CGTMSE basis other than year-1-guaranteed). The offer is
    then non-comparable and never priced, instead of failing the stage or lowering an APR."""
    bad: list[str] = []
    principal, rate = _number(offer["principal"]), _number(offer["annual_rate"])
    if principal is None or principal <= 0:
        bad.append("principal")
    if rate is None or not 0 < rate <= 1:  # stored as a fraction: 0.1205 is 12.05% a year
        bad.append("annual_rate")
    tenure, moratorium = _number(offer["tenure_months"]), _number(offer.get("moratorium_months", 0))
    tenure_ok = tenure is not None and tenure == int(tenure) and 1 <= tenure <= MAX_TENURE_MONTHS
    if not tenure_ok:
        bad.append("tenure_months")
    if moratorium is None or moratorium != int(moratorium) or moratorium < 0:
        bad.append("moratorium_months")
    elif tenure_ok and tenure is not None and moratorium >= tenure:
        bad.append("moratorium_months")
    for fee in offer["fees"] or ():
        value = _number(fee.get("value"))
        cap = Decimal(1) if fee.get("basis") == "pct_of_principal" else None
        if value is None or value < 0 or (cap is not None and value > cap):
            bad.append("fees")
            break
    insurance = offer.get("insurance")
    if insurance:
        premium = _number(insurance.get("premium"))
        if premium is None or premium < 0:
            bad.append("insurance.premium")
        if insurance.get("financed"):
            bad.append("insurance.financed")
    guarantee = offer.get("guarantee")
    if guarantee and guarantee.get("passed_to_borrower"):
        pct = _number(guarantee.get("annual_fee_pct"))
        if pct is None or not 0 <= pct < 1:
            bad.append("guarantee.annual_fee_pct")
        if guarantee.get("basis", CGTMSE_BASIS) != CGTMSE_BASIS:
            bad.append("guarantee.basis")
    return tuple(bad)


def audit(
    offer: Mapping[str, Any],
    hidden: Sequence[Charge],
    enterprise_class: str,
    unpriced: Sequence[str] = (),
) -> Audit:
    """``unpriced``: schedule rows the offer leaves out whose amount code cannot read. They are
    flagged as hidden charges and make the offer non-comparable (fail closed, BRD §14)."""
    missing = tuple(t for t in MATERIAL_TERMS if t not in offer)
    if missing:
        missing_flags = tuple(f"{BlockerCode.LW_MISSING_MATERIAL_TERM}:{t}" for t in missing)
        return Audit(str(offer["offer_id"]), False, missing_flags, missing)
    invalid = invalid_terms(offer)
    if invalid:  # nothing below can be computed on these values (instalment, dates, pricing)
        invalid_flags = tuple(f"{BlockerCode.LW_OFFER_INVALID}:{t}" for t in invalid)
        return Audit(str(offer["offer_id"]), False, invalid_flags, (), invalid)
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
    flags += [f"{BlockerCode.LW_HIDDEN_CHARGE}:{name}:unpriced" for name in unpriced]
    if offer["rate_type"] == "floating":
        flags.append(BlockerCode.LW_RATE_MAY_RESET)
        if offer.get("benchmark") != "EBLR" and enterprise_class in {"micro", "small"}:
            flags.append(BlockerCode.LW_BENCHMARK_NOT_EXTERNAL)
    if offer.get("guarantee") and enterprise_class == "medium":
        flags.append(BlockerCode.LW_CGTMSE_INELIGIBLE)
    blocking = {BlockerCode.LW_INSTALMENT_MISMATCH, BlockerCode.LW_SCHEDULE_DATE_MISMATCH}
    comparable = not blocking & set(flags) and not unpriced
    return Audit(str(offer["offer_id"]), comparable, tuple(str(f) for f in flags))


@dataclass(frozen=True)
class ScheduleRow:
    """One charge row of a lender's schedule of charges (``<kfs_doc_id>-SCH``, ADR 0021)."""

    name: str
    timing: str
    amount_text: str  # verbatim cell, e.g. "0.84% of the loan amount + GST"


def parse_schedule(text: str) -> list[ScheduleRow]:
    """Charge rows of a schedule table. Lines that are not charge rows (headers, prose, a planted
    instruction) are ignored, so document text never becomes a charge or an instruction."""
    rows = []
    for line in text.splitlines():
        m = _ROW.match(line.strip())
        if m:
            rows.append(ScheduleRow(m.group(1), m.group(2), m.group(3)))
    return rows


def row_charge(name: str, timing: str, amount_text: str) -> Charge | None:
    """``amount_text`` -> a priced charge: "x% of the loan amount" or "₹n", "+ GST" when taxed.
    None when it cannot be read (the charge is then not priced, like gold)."""
    found = find_all(amount_text)
    if len(found) != 1 or timing not in ("upfront", "monthly", "annual"):
        return None
    hit, gst = found[0], not _UNTAXED.search(amount_text)  # LW-06: taxed unless stated exempt
    if hit.kind == "rate" and "of the loan amount" in amount_text:
        return Charge(name, "pct_of_principal", dec(hit.value), timing, gst)  # type: ignore[arg-type]
    if hit.kind == "money":
        return Charge(name, "fixed", dec(hit.value), timing, gst)  # type: ignore[arg-type]
    return None


def unpriced_rows(offer: Mapping[str, Any], rows: Sequence[ScheduleRow]) -> list[str]:
    """Undeclared schedule rows whose amount cannot be read: never silently dropped (LW-04)."""
    declared = {f["name"] for f in offer.get("fees", [])}
    return [
        r.name
        for r in rows
        if r.name not in declared and row_charge(r.name, r.timing, r.amount_text) is None
    ]


def hidden_charges(offer: Mapping[str, Any], rows: Sequence[ScheduleRow]) -> list[Charge]:
    """LW-04: schedule rows whose name the offer record does not declare."""
    declared = {f["name"] for f in offer.get("fees", [])}
    out = []
    for row in rows:
        if row.name in declared:
            continue
        charge = row_charge(row.name, row.timing, row.amount_text)
        if charge is not None:
            out.append(charge)
    return out
