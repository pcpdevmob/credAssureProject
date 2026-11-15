"""Loan cost: schedule, borrower cash flows, IRR and APR (LW-05..08, BR-08, ADR 0012/0021).

Pure and Decimal only (prec 34).
- Month 0: principal minus upfront charges (+ GST where flagged), insurance that is not
  financed, year-1 annual charges and the year-1 CGTMSE fee on the guaranteed amount.
- Months 1..tenure: interest only during the moratorium, then the EMI (or equal principal),
  plus monthly charges; annual charges recur at months 12, 24, ... below the tenure; CGTMSE
  is charged on the outstanding principal at each anniversary.
- GST applies to charges, never to interest. Charges in the lender's schedule of charges but
  missing from the offer (hidden, LW-04) are priced in like any other charge.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any, Literal

from credassure.core.money import MONEY

TOLERANCE = Decimal("1e-12")
MAX_ITERATIONS = 200
CGTMSE_BASIS = "y1_guaranteed_then_outstanding"


class IRRNotFoundError(ValueError):
    """The cash flows have no internal rate of return in (-99%, 100%) per period."""


@dataclass(frozen=True)
class Charge:
    name: str
    basis: Literal["fixed", "pct_of_principal"]
    value: Decimal
    timing: Literal["upfront", "monthly", "annual"]
    gst_applicable: bool = True


@dataclass(frozen=True)
class Priced:
    apr: Decimal  # fraction, e.g. 0.1300 for 13.00%
    amount_received: Decimal
    total_repayment: Decimal
    total_cost: Decimal
    flows: tuple[Decimal, ...]


def dec(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        raise TypeError("money and rates are never float (BR-05)")
    return Decimal(str(value))


def charges(offer: Mapping[str, Any], hidden: Sequence[Charge] = ()) -> list[Charge]:
    declared = [
        Charge(
            f["name"], f["basis"], dec(f["value"]), f["timing"], bool(f.get("gst_applicable", True))
        )
        for f in offer.get("fees", [])
    ]
    return [*declared, *hidden]


def gst_total(
    offer: Mapping[str, Any], hidden: Sequence[Charge] = (), *, gst_rate: Decimal
) -> Decimal:
    """Every rupee of GST the borrower pays over the loan: on charges flagged ``gst_applicable``
    and on a CGTMSE fee passed on with ``gst_applicable``; never on interest (D7, BR-08)."""
    with localcontext(MONEY):
        untaxed = cash_flows(offer, hidden, gst_rate=Decimal(0))
        taxed = cash_flows(offer, hidden, gst_rate=gst_rate)
        return sum((a - b for a, b in zip(untaxed, taxed, strict=True)), Decimal(0))


def instalment(offer: Mapping[str, Any]) -> Decimal:
    """First amortising instalment from principal, rate and tenure (exact; LW-03 compares to ₹1)."""
    with localcontext(MONEY):
        principal = dec(offer["principal"])
        monthly = dec(offer["annual_rate"]) / 12
        n = int(offer["tenure_months"]) - int(offer.get("moratorium_months", 0))
        if offer["repayment"]["method"] == "equal_principal":
            return principal / n + principal * monthly
        growth = (1 + monthly) ** n
        return principal * monthly * growth / (growth - 1)


def cash_flows(
    offer: Mapping[str, Any], hidden: Sequence[Charge] = (), *, gst_rate: Decimal
) -> list[Decimal]:
    with localcontext(MONEY):
        principal = dec(offer["principal"])
        monthly = dec(offer["annual_rate"]) / 12
        tenure, moratorium = int(offer["tenure_months"]), int(offer.get("moratorium_months", 0))
        n = tenure - moratorium
        flows = [Decimal(0)] * (tenure + 1)
        flows[0] = principal
        for c in charges(offer, hidden):
            amount = c.value * principal if c.basis == "pct_of_principal" else c.value
            amount *= (1 + gst_rate) if c.gst_applicable else 1
            months = {
                "upfront": [0],
                "annual": list(range(0, tenure, 12)),
                "monthly": list(range(1, tenure + 1)),
            }[c.timing]
            for k in months:
                flows[k] -= amount
        insurance = offer.get("insurance")
        if insurance:
            if insurance["financed"]:
                raise NotImplementedError(
                    "financed insurance has no agreed convention yet (ADR 0021)"
                )
            flows[0] -= dec(insurance["premium"])
        emi = instalment(offer)
        balance, outstanding = principal, [principal]
        for k in range(1, tenure + 1):
            interest = balance * monthly
            if k <= moratorium:
                pay, repaid = interest, Decimal(0)
            elif offer["repayment"]["method"] == "equal_principal":
                repaid = principal / n
                pay = repaid + interest
            else:
                pay, repaid = emi, emi - interest
            balance -= repaid
            outstanding.append(balance)
            flows[k] -= pay
        guarantee = offer.get("guarantee")
        if guarantee and guarantee["passed_to_borrower"]:
            if guarantee.get("basis", CGTMSE_BASIS) != CGTMSE_BASIS:
                raise NotImplementedError(
                    f"CGTMSE basis {guarantee['basis']} is not priced (ADR 0021)"
                )
            rate = dec(guarantee["annual_fee_pct"]) * (
                (1 + gst_rate) if guarantee["gst_applicable"] else 1
            )
            flows[0] -= principal * rate  # year 1 on the guaranteed amount (R-CG-02)
            for k in range(12, tenure, 12):
                flows[k] -= outstanding[k] * rate
        return flows


def _npv(rate: Decimal, flows: Sequence[Decimal]) -> tuple[Decimal, Decimal]:
    value, slope, factor = Decimal(0), Decimal(0), Decimal(1)
    base = 1 + rate
    for k, flow in enumerate(flows):
        value += flow / factor
        slope -= k * flow / (factor * base)
        factor *= base
    return value, slope


def irr(flows: Sequence[Decimal]) -> Decimal:
    """Periodic IRR: Newton-Raphson, then bisection if it strays (tol 1e-12, 200 iterations)."""
    with localcontext(MONEY):
        rate = Decimal("0.01")
        for _ in range(MAX_ITERATIONS):
            try:
                value, slope = _npv(rate, flows)
                step = value / slope
            except (InvalidOperation, ZeroDivisionError):
                break
            rate -= step
            if rate <= Decimal("-0.99") or rate >= 1:
                break
            if abs(step) < TOLERANCE:
                return rate
        low, high = Decimal("-0.99"), Decimal("1")
        f_low, f_high = _npv(low, flows)[0], _npv(high, flows)[0]
        if f_low == 0:
            return low
        if f_high == 0:
            return high
        if f_low * f_high > 0:
            raise IRRNotFoundError("no sign change between -99% and 100% per period")
        for _ in range(MAX_ITERATIONS):
            mid = (low + high) / 2
            if abs(high - low) < TOLERANCE:
                return mid
            f_mid = _npv(mid, flows)[0]
            if f_mid == 0:
                return mid
            if (f_mid < 0) == (f_low < 0):
                low, f_low = mid, f_mid
            else:
                high = mid
        raise IRRNotFoundError("bisection did not converge")


def annualise(
    periodic: Decimal, convention: Literal["nominal", "effective"] = "nominal"
) -> Decimal:
    with localcontext(MONEY):
        return periodic * 12 if convention == "nominal" else (1 + periodic) ** 12 - 1


def price(
    offer: Mapping[str, Any],
    hidden: Sequence[Charge] = (),
    *,
    gst_rate: Decimal,
    convention: Literal["nominal", "effective"] = "nominal",
) -> Priced:
    flows = cash_flows(offer, hidden, gst_rate=gst_rate)
    with localcontext(MONEY):
        received = flows[0]
        repayment = -sum(flows[1:], Decimal(0))
        return Priced(
            annualise(irr(flows), convention),
            received,
            repayment,
            repayment - received,
            tuple(flows),
        )
