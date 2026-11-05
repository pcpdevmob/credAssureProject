"""Gold for the funding need (WC-01..06, BR-01, BR-02). Floats are fine here; answers are compared to ₹1.

Conventions (DATA_SPEC §2 and the case generator header):
- cumulative cash at the end of week t = opening cash + confirmed receipts + receivables in their
  expected week - costs - payables in their due week, for weeks 1..t; rows after week 26 are ignored;
- peak shortfall = -(lowest cumulative cash) when below zero;
- need = max(0, peak + buffer - undrawn limits - confirmed mitigations), rounded up to ₹1 lakh;
- mitigations offset the need only (they are not inflows).
"""

import math
from collections import Counter
from typing import Any

from .data import INDICATIVE, LAKH, WEEKS, amount, case

REQUIRED_OPENING = ("as_of_week_start", "opening_cash", "min_cash_buffer", "credit_lines")


def validate(case_id: str) -> list[dict[str, str]]:
    """Blockers that stop the funding stage (NEEDS_INPUT): missing fields and contradictions (WC-01/02)."""
    c = case(case_id)
    blockers = [
        {"code": "WC_MISSING_FIELD", "field": f} for f in REQUIRED_OPENING if f not in c["opening"]
    ]
    order_receipts = sum(
        amount(r["amount"])
        for r in c["receipts"]
        if r["source"] in {"order_advance", "order_milestone"} and r["confirmed"] == "true"
    )
    if abs(order_receipts - float(c["order"]["order_value"])) > 1:
        blockers.append({"code": "WC_CONFLICT_TOTALS", "field": "receipts"})
    dupes = [k for k, n in Counter(r["invoice_id"] for r in c["receivables"]).items() if n > 1]
    if dupes:
        blockers.append({"code": "WC_DUPLICATE_ID", "field": "receivables.invoice_id"})
    if [k for k, n in Counter(r["bill_id"] for r in c["payables"]).items() if n > 1]:
        blockers.append({"code": "WC_DUPLICATE_ID", "field": "payables.bill_id"})
    return blockers


def cash_path(case_id: str) -> list[float]:
    """Cumulative cash at the end of weeks 1..26 (index 0 is week 1)."""
    c = case(case_id)
    net = [0.0] * (WEEKS + 1)
    for r in c["costs"]:
        net[int(r["week"])] -= amount(r["amount"])
    for r in c["receipts"]:
        if r["confirmed"] == "true" and int(r["week"]) <= WEEKS:
            net[int(r["week"])] += amount(r["amount"])
    for r in c["receivables"]:
        if int(r["expected_week"]) <= WEEKS:
            net[int(r["expected_week"])] += amount(r["amount"])
    for r in c["payables"]:
        if int(r["due_week"]) <= WEEKS:
            net[int(r["due_week"])] -= amount(r["amount"])
    path, cum = [], float(c["opening"]["opening_cash"])
    for week in range(1, WEEKS + 1):
        cum += net[week]
        path.append(cum)
    return path


def available_limits(case_id: str, by_week: int | None = None) -> tuple[float, float]:
    """Undrawn sanctioned limits, and confirmed mitigations that have evidence and arrive by ``by_week``
    (WC-05: offsets only from supplied records; a mitigation after the peak cannot cover it)."""
    opening = case(case_id)["opening"]
    undrawn = sum(
        float(x["sanctioned"]) - float(x["drawn"]) for x in opening.get("credit_lines", [])
    )
    mitigations = sum(
        float(x["amount"])
        for x in opening.get("confirmed_mitigations", [])
        if x.get("evidence_ref") and (by_week is None or int(x["week"]) <= by_week)
    )
    return undrawn, mitigations


def funding(case_id: str) -> dict[str, Any]:
    blockers = validate(case_id)
    if blockers:
        return {"gate": "NEEDS_INPUT", "blockers": blockers}
    path = cash_path(case_id)
    low = min(path)
    peak = max(0.0, -low)
    peak_week = path.index(low) + 1
    buffer = float(case(case_id)["opening"]["min_cash_buffer"])
    undrawn, mitigations = available_limits(case_id, by_week=peak_week)
    raw = max(0.0, peak + buffer - undrawn - mitigations)
    need = math.ceil(round(raw, 2) / LAKH) * LAKH
    bridge = [
        ("indicative_request", float(INDICATIVE)),
        ("peak_shortfall_vs_request", peak - INDICATIVE),
        ("min_cash_buffer", buffer),
        ("undrawn_credit_limits", -undrawn),
        ("confirmed_mitigations", -mitigations),
        ("floor_at_zero", raw - (peak + buffer - undrawn - mitigations)),
        ("round_up_to_lakh", need - raw),
    ]
    return {
        "gate": "GO",
        "peak_shortfall": round(peak, 2),
        "peak_week": peak_week,
        "shortfall_weeks": sum(1 for x in path if x < 0),
        "min_cash_buffer": buffer,
        "undrawn_limits": undrawn,
        "mitigations": mitigations,
        "recommended_amount": need,
        "bridge": [{"line": k, "amount": round(v, 2)} for k, v in bridge],
    }
