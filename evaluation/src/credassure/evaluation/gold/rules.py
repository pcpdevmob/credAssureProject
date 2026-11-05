"""Gold for routing (APR-01..03, BR-12), onboarding (ONB-02/03, BR-04) and negotiation (LW-12/13, BR-09/10)."""

from datetime import date
from typing import Any

from . import offers as offer_gold
from .data import AS_OF, hr_profiles, lender_scripts, offers, parse_date

THRESHOLD = 15_000_000  # ₹1,50,00,000 (BRD §8.8)
AUTHORISED = {"credit_proposal_officer", "senior_finance_analyst"}
TRAININGS = ("AML-201", "DPDP-101", "FIN-101")
POLICY_VERSION = "v3"


def route(amount: float, boundary_rule: str = "hold") -> str:
    """vp above, director below, the configured rule at exactly ₹1.5 crore (default hold)."""
    if amount > THRESHOLD:
        return "vp_finance"
    if amount < THRESHOLD:
        return "director_finance"
    return {"hold": "HELD", "director": "director_finance", "vp": "vp_finance"}[boundary_rule]


def onboarding(emp_id: str, as_of: date = AS_OF) -> dict[str, Any]:
    profile = next(p for p in hr_profiles() if p["emp_id"] == emp_id)
    rules: dict[str, str] = {"role": "PASS" if profile["role"] in AUTHORISED else "FAIL"}
    if profile["role"] in AUTHORISED:
        records = {t["code"]: t for t in profile["trainings"]}
        for code in TRAININGS:
            t = records.get(code)
            if t is None:
                rules[code] = "UNKNOWN"
            elif t["status"] != "completed" or not t.get("expires_on"):
                rules[code] = "FAIL"
            else:
                rules[code] = "PASS" if parse_date(t["expires_on"]) >= as_of else "FAIL"
        rules["policy_ack"] = (
            "PASS" if profile.get("policy_ack_version") == POLICY_VERSION else "FAIL"
        )
    if "FAIL" in rules.values():
        gate = "NO_GO"
    elif "UNKNOWN" in rules.values():
        gate = "NEEDS_INPUT"
    else:
        gate = "GO"
    return {
        "gate": gate,
        "rules": rules,
        "failed": sorted(k for k, v in rules.items() if v != "PASS"),
    }


def negotiation(case_id: str) -> dict[str, Any]:
    """Fee-waiver round 1: the comparable offer with the highest processing fee asks for a waiver citing
    the lowest verified processing fee of another comparable offer; no competitor, no message (BR-10).
    A concession counts only from the re-audited revised version (BR-09)."""
    compared = offer_gold.compare(case_id)
    comparable = {a["offer_id"] for a in compared["offers"] if a.get("comparable")}
    v1 = {
        o["offer_id"]: o
        for o in offers(case_id)
        if o["version"] == 1 and o["offer_id"] in comparable
    }

    def fee(o: dict[str, Any]) -> float:
        return next((float(f["value"]) for f in o["fees"] if f["name"] == "Processing fee"), 0.0)

    if len(v1) < 2:
        return {"message": None, "reason": "no verified competing fee"}
    target = max(v1.values(), key=fee)
    competitor = min((o for o in v1.values() if o is not target), key=fee)
    script = lender_scripts()[target["lender_id"]]["responses"]["fee_waiver_v1"]
    v2 = next(
        (o for o in offers(case_id) if o["offer_id"] == target["offer_id"] and o["version"] == 2),
        None,
    )
    result: dict[str, Any] = {
        "target_offer": target["offer_id"],
        "slots": {
            "lender_name": target["lender_name"],
            "current_fee_pct": round(fee(target) * 100, 4),
            "competing_fee_pct": round(fee(competitor) * 100, 4),
        },
        "lender_response": script["type"],
        "injection_in_reply": script["type"] == "injection",
        "apr_v1_pct": next(
            a["apr_pct"] for a in compared["offers"] if a["offer_id"] == target["offer_id"]
        ),
    }
    if v2 is not None:
        audited = offer_gold.audit(case_id, v2)
        result["apr_v2_pct"] = audited["apr_pct"]
        # BR-09 / LW-13: a concession counts only when the received version re-audits clean and is cheaper
        result["concession_counts"] = bool(audited["comparable"]) and fee(v2) < fee(target)
    else:
        result["apr_v2_pct"] = None
        result["concession_counts"] = False
    return result
