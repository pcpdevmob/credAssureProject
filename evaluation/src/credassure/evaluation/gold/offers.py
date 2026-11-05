"""Gold for the lender comparison (LW-02..11, LW-14, BR-06, BR-07).

- comparable: every material term present and the stated instalment within ₹1 of the recomputed one;
- affordable (LW-09): for every week of the cash table, cash + undrawn limits + confirmed mitigations +
  the amount received (from the disbursal week) - every borrower payment so far >= the minimum buffer;
  payment k falls on disbursal + k calendar months;
- late or short (LW-10): disbursal after the peak-shortfall week, or principal below the need;
- eligible = comparable, affordable, not late or short; ranked by APR, then total cost, then disbursal date;
- gate GO only with at least two eligible offers (LW-14).
"""

from typing import Any

from . import cashflow, loancost
from .data import add_months, case, offers, parse_date, week_of

MATERIAL = ("principal", "annual_rate", "tenure_months", "fees", "repayment", "disbursal_date")


def audit(case_id: str, offer: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in MATERIAL if k not in offer]
    flags = [f"LW_MISSING_MATERIAL_TERM:{k}" for k in missing]
    result: dict[str, Any] = {
        "offer_id": offer["offer_id"],
        "version": offer["version"],
        "flags": flags,
    }
    if missing:
        result["comparable"] = False
        return result
    first_due = add_months(
        parse_date(offer["disbursal_date"]), int(offer.get("moratorium_months", 0)) + 1
    )
    if parse_date(offer["first_repayment_date"]) != first_due:
        flags.append(
            "LW_SCHEDULE_DATE_MISMATCH"
        )  # payments are scheduled from disbursal (ADR 0021)
    stated = offer.get("stated_instalment")
    if stated is not None and abs(float(stated) - loancost.instalment(offer)) > 1:
        flags.append("LW_INSTALMENT_MISMATCH")
    hidden = loancost.hidden_charges(offer)
    flags += [f"LW_HIDDEN_CHARGE:{h['name']}" for h in hidden]
    if offer["rate_type"] == "floating":
        flags.append("LW_RATE_MAY_RESET")
        if offer.get("benchmark") != "EBLR" and case(case_id)["order"]["enterprise_class"] in {
            "micro",
            "small",
        }:
            flags.append("LW_BENCHMARK_NOT_EXTERNAL")
    if offer.get("guarantee") and case(case_id)["order"]["enterprise_class"] == "medium":
        flags.append("LW_CGTMSE_INELIGIBLE")
    result |= loancost.price(offer, hidden)
    result["comparable"] = not {"LW_INSTALMENT_MISMATCH", "LW_SCHEDULE_DATE_MISMATCH"} & set(flags)
    result["_hidden"] = hidden
    return result


def lowest_cash(case_id: str, offer: dict[str, Any], hidden: list[dict[str, Any]]) -> float:
    path = cashflow.cash_path(case_id)
    undrawn, mitigations = cashflow.available_limits(case_id)
    f = loancost.flows(offer, hidden)
    disbursal = parse_date(offer["disbursal_date"])
    paid = [0.0] * (len(path) + 1)
    for k in range(1, len(f)):
        week = week_of(add_months(disbursal, k))
        if 1 <= week <= len(path):
            paid[week] -= f[k]
    received_week = week_of(disbursal)
    lowest, cumulative = float("inf"), 0.0
    for week in range(1, len(path) + 1):
        cumulative += paid[week]
        received = f[0] if week >= received_week else 0.0
        lowest = min(lowest, path[week - 1] + undrawn + mitigations + received - cumulative)
    return lowest


def compare(case_id: str) -> dict[str, Any]:
    funding = cashflow.funding(case_id)
    results = []
    for offer in (o for o in offers(case_id) if o["version"] == 1):
        a = audit(case_id, offer)
        if funding["gate"] == "GO" and a["comparable"]:
            low = lowest_cash(case_id, offer, a["_hidden"])
            a["lowest_cash"] = round(low, 2)
            a["affordable"] = low >= funding["min_cash_buffer"]
            if not a["affordable"]:
                a["flags"].append("LW_NOT_AFFORDABLE")
            late = week_of(parse_date(offer["disbursal_date"])) > funding["peak_week"]
            short = float(offer["principal"]) < funding["recommended_amount"]
            if late or short:
                a["flags"].append("LW_LATE_OR_SHORT")
            a["eligible"] = a["affordable"] and not late and not short
        else:
            a["eligible"] = False
        a.pop("_hidden", None)
        results.append(a)
    by_id = {o["offer_id"]: o for o in offers(case_id) if o["version"] == 1}
    eligible = sorted(
        (a for a in results if a["eligible"]),
        key=lambda a: (a["apr_pct"], a["total_cost"], by_id[a["offer_id"]]["disbursal_date"]),
    )
    ranking = [a["offer_id"] for a in eligible]
    if funding["gate"] != "GO":
        gate = "NEEDS_INPUT"
    elif funding["recommended_amount"] == 0:
        gate, ranking = "NOT_REQUIRED", []  # no funding need: no loan to compare (ADR 0021)
    else:
        gate = "GO" if len(ranking) >= 2 else "NO_GO"
    return {"gate": gate, "ranking": ranking, "offers": results}
