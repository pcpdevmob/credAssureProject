"""Gold for loan cost (LW-05..08, BR-08): borrower cash flows, nominal APR (monthly IRR x 12, ADR 0012).

Conventions (offer generator header, DATA_SPEC §3):
- month 0 (disbursal): principal minus upfront fees (+ GST where flagged), insurance not financed, annual
  charges for year 1 and the year-1 CGTMSE fee on the guaranteed amount (+ GST where flagged);
- monthly payments for months 1..tenure: interest only during the moratorium, then the EMI on the full
  principal over tenure - moratorium months (or equal principal); monthly charges every month;
- annual charges again at months 12, 24, ...; CGTMSE on the outstanding principal at each anniversary;
- GST applies to fees and charges only, never to interest (R-GST-01, R-GST-02);
- charges found in the offer's schedule of charges but missing from the offer record (hidden, LW-04) are
  priced in like any other fee (ADR 0021).
"""

import re
from typing import Any

import numpy_financial as npf  # type: ignore[import-untyped]

from .data import gst_rate, kfs_text

ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*(upfront|monthly|annual)\s*\|\s*([^|]+?)\s*\|$")


def fee_amount(fee: dict[str, Any], principal: float) -> float:
    value = float(fee["value"])
    return value * principal if fee["basis"] == "pct_of_principal" else value


def hidden_charges(offer: dict[str, Any]) -> list[dict[str, Any]]:
    """Charges in the offer's schedule of charges (``<kfs_doc_id>-SCH``) that the offer record omits (LW-04)."""
    declared = {f["name"] for f in offer.get("fees", [])}
    found = []
    for line in kfs_text(f"{offer['kfs_doc_id']}-SCH").splitlines():
        m = ROW.match(line.strip())
        if not m or m.group(1) in declared:
            continue
        name, timing, text = m.groups()
        pct = re.match(r"([\d.]+)% of the loan amount", text)
        rupees = re.match(r"₹([\d,]+)", text)
        if pct:
            fee = {"name": name, "basis": "pct_of_principal", "value": float(pct.group(1)) / 100}
        elif rupees:
            fee = {"name": name, "basis": "fixed", "value": float(rupees.group(1).replace(",", ""))}
        else:
            continue
        found.append(fee | {"timing": timing, "gst_applicable": "+ GST" in text})
    return found


def instalment(offer: dict[str, Any]) -> float:
    """First amortising instalment recomputed from rate, tenure and principal (LW-03)."""
    principal, r = float(offer["principal"]), float(offer["annual_rate"]) / 12
    n = int(offer["tenure_months"]) - int(offer.get("moratorium_months", 0))
    if offer["repayment"]["method"] == "equal_principal":
        return principal / n + principal * r
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def flows(offer: dict[str, Any], hidden: list[dict[str, Any]] | None = None) -> list[float]:
    principal = float(offer["principal"])
    r = float(offer["annual_rate"]) / 12
    tenure, moratorium = offer["tenure_months"], offer.get("moratorium_months", 0)
    n = tenure - moratorium
    gst = gst_rate()
    f = [0.0] * (tenure + 1)
    f[0] = principal
    for fee in [*offer.get("fees", []), *(hidden or [])]:
        charge = fee_amount(fee, principal) * (1 + gst if fee.get("gst_applicable", True) else 1)
        if fee["timing"] == "upfront":
            f[0] -= charge
        elif fee["timing"] == "annual":
            for k in range(0, tenure, 12):
                f[k] -= charge
        else:
            for k in range(1, tenure + 1):
                f[k] -= charge
    if offer.get("insurance") and offer["insurance"]["financed"]:
        raise NotImplementedError("financed insurance has no agreed convention yet (ADR 0021)")
    if offer.get("insurance"):
        f[0] -= float(offer["insurance"]["premium"])
    emi = instalment(offer)
    balance = principal
    outstanding = [principal]
    for k in range(1, tenure + 1):
        interest = balance * r
        if k <= moratorium:
            pay, repaid = interest, 0.0
        elif offer["repayment"]["method"] == "equal_principal":
            repaid = principal / n
            pay = repaid + interest
        else:
            pay = emi
            repaid = pay - interest
        balance -= repaid
        outstanding.append(balance)
        f[k] -= pay
    guarantee = offer.get("guarantee")
    if guarantee and guarantee["passed_to_borrower"]:
        if (
            guarantee.get("basis", "y1_guaranteed_then_outstanding")
            != "y1_guaranteed_then_outstanding"
        ):
            raise NotImplementedError(f"CGTMSE basis {guarantee['basis']} not priced by gold")
        rate = float(guarantee["annual_fee_pct"]) * (1 + gst if guarantee["gst_applicable"] else 1)
        f[0] -= principal * rate  # year 1 on the guaranteed amount (R-CG-02)
        for k in range(12, tenure, 12):
            f[k] -= outstanding[k] * rate  # later years on the outstanding amount
    return f


def price(offer: dict[str, Any], hidden: list[dict[str, Any]] | None = None) -> dict[str, float]:
    f = flows(offer, hidden)
    received = f[0]
    repayment = -sum(f[1:])
    return {
        "apr_pct": round(float(npf.irr(f)) * 12 * 100, 2),
        "amount_received": round(received, 2),
        "total_repayment": round(repayment, 2),
        "total_cost": round(repayment - received, 2),
    }
