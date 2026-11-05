"""Phase 3: independent gold reproduces the design, every plant and the RBI KFS APR illustration."""

import json

import numpy_financial as npf  # type: ignore[import-untyped]
import pytest
import yaml

from credassure.evaluation.gold import cashflow, offers, rules
from credassure.evaluation.gold.data import DATA, REPO, case_ids, hr_profiles

DESIGNS = {
    d["case_id"]: d
    for d in json.loads((DATA / "_design" / "designs.json").read_text(encoding="utf-8"))
}
PLANTS = json.loads((DATA / "plants.json").read_text(encoding="utf-8"))
GOLD_SRC = REPO / "evaluation" / "src" / "credassure" / "evaluation" / "gold"


def _tags(item_id: str) -> set[str]:
    return {p["plant"] for p in PLANTS if p["id"] == item_id}


@pytest.mark.parametrize("case_id", case_ids())
def test_WC03_gold_matches_design_three_way(case_id: str) -> None:
    gold = cashflow.funding(case_id)
    design = DESIGNS[case_id]
    if gold["gate"] == "NEEDS_INPUT":
        assert DESIGNS[case_id]["expected_gate"] == "NEEDS_INPUT"
        return
    assert gold["recommended_amount"] == design["design_need"]
    assert round(gold["peak_shortfall"]) == design["design_peak_shortfall"]
    assert gold["peak_week"] == design["design_peak_week"]


@pytest.mark.parametrize("case_id", case_ids())
def test_WC06_bridge_sums_exactly_and_need_is_non_negative(case_id: str) -> None:
    gold = cashflow.funding(case_id)
    if gold["gate"] != "GO":
        return
    assert round(sum(line["amount"] for line in gold["bridge"]), 2) == gold["recommended_amount"]
    assert gold["recommended_amount"] >= 0


def test_WC01_needs_input_cases_name_their_blockers() -> None:
    assert cashflow.funding("CA-2026-0013")["blockers"] == [
        {"code": "WC_MISSING_FIELD", "field": "min_cash_buffer"}
    ]
    codes = {b["code"] for b in cashflow.funding("CA-2026-0014")["blockers"]}
    assert codes == {"WC_CONFLICT_TOTALS", "WC_DUPLICATE_ID"}


@pytest.mark.parametrize("case_id", case_ids())
def test_LW_every_offer_plant_holds_in_gold(case_id: str) -> None:
    """Review item S6: plants are confirmed by independent gold before G1, not only by design."""
    result = offers.compare(case_id)
    by_id = {a["offer_id"]: a for a in result["offers"]}
    priced = [a for a in result["offers"] if "apr_pct" in a]
    for offer_id, a in by_id.items():
        tags, flags = _tags(offer_id), " ".join(a["flags"])
        if {"missing_tenure", "missing_fees"} & tags:
            assert "LW_MISSING_MATERIAL_TERM" in flags
        if "mismatch" in tags:
            assert "LW_INSTALMENT_MISMATCH" in flags
        if "hidden" in tags:
            assert "LW_HIDDEN_CHARGE" in flags
        if {"eblr", "mclr"} & tags:
            assert "LW_RATE_MAY_RESET" in flags
        if "mclr" in tags:
            assert "LW_BENCHMARK_NOT_EXTERNAL" in flags
        if "headline" in tags:  # lowest headline rate, highest APR among priced offers
            assert a["apr_pct"] == max(p["apr_pct"] for p in priced)
        if result["gate"] == "NEEDS_INPUT":
            continue
        if "unaffordable" in tags:
            assert "LW_NOT_AFFORDABLE" in flags
            assert a["apr_pct"] == min(p["apr_pct"] for p in priced)
        if {"late", "short"} & tags:
            assert "LW_LATE_OR_SHORT" in flags
    if result["gate"] == "NOT_REQUIRED":  # need is ₹0: no loan to compare (ADR 0021)
        assert result["ranking"] == [] and cashflow.funding(case_id)["recommended_amount"] == 0
    elif result["gate"] != "NEEDS_INPUT":
        eligible = next(
            p["plant"] for p in PLANTS if p["id"] == case_id and p["plant"].startswith("eligible_")
        )
        assert len(result["ranking"]) == int(eligible.split("_")[1])


def test_LW11_unaffordable_offer_is_never_ranked_first() -> None:
    for case_id in case_ids():
        result = offers.compare(case_id)
        if result["ranking"]:
            first = next(a for a in result["offers"] if a["offer_id"] == result["ranking"][0])
            assert "LW_NOT_AFFORDABLE" not in first["flags"]


def test_LW05_apr_at_least_nominal_rate_when_fees_exist() -> None:
    for case_id in case_ids():
        for a in offers.compare(case_id)["offers"]:
            offer = next(
                o
                for o in offers.offers(case_id)
                if o["offer_id"] == a["offer_id"] and o["version"] == 1
            )
            if "apr_pct" in a and offer.get("fees"):
                assert a["apr_pct"] >= float(offer["annual_rate"]) * 100


def test_ADR0012_gold_reproduces_the_rbi_kfs_apr_illustration() -> None:
    fixture = yaml.safe_load(
        (REPO / "evaluation" / "gold" / "fixtures" / "rbi_kfs_apr_illustration.yaml").read_text(
            encoding="utf-8"
        )
    )
    inputs, published = fixture["inputs"], fixture["published"]
    flows = [float(inputs["net_disbursed"])] + [-float(inputs["instalment_exact"])] * inputs[
        "tenure_months"
    ]
    assert round(float(npf.irr(flows)) * 12 * 100, 2) == float(published["apr_pct"])


def test_APR01_03_routing_boundary_all_rules() -> None:
    assert rules.route(14_999_999) == "director_finance"
    assert rules.route(15_000_001) == "vp_finance"
    assert {rules.route(15_000_000, r) for r in ("hold", "director", "vp")} == {
        "HELD",
        "director_finance",
        "vp_finance",
    }


def test_ONB03_onboarding_gold_matches_hr_plants() -> None:
    expected = {
        "go": "GO",
        "training_expired": "NO_GO",
        "training_missing": "NEEDS_INPUT",
        "role_not_authorised": "NO_GO",
        "ack_missing_or_old": "NO_GO",
        "training_in_progress": "NO_GO",
        "expired_and_ack_missing": "NO_GO",
    }
    for profile in hr_profiles():
        (plant,) = _tags(profile["emp_id"])
        assert rules.onboarding(profile["emp_id"])["gate"] == expected[plant], profile["emp_id"]
    assert rules.onboarding("E020")["failed"] == ["FIN-101", "policy_ack"]  # both failures named


def test_BR09_concession_counts_only_with_a_reaudited_revision() -> None:
    for case_id in case_ids():
        n = rules.negotiation(case_id)
        if n.get("lender_response") == "refusal":
            assert n["concession_counts"] is False and n["apr_v2_pct"] is None
        if n.get("concession_counts"):
            assert n["apr_v2_pct"] < n["apr_v1_pct"]


def test_gold_never_reads_design_intent_or_engines() -> None:
    import re

    forbidden = re.compile(
        r"""["']_design["']|^\s*(?:from|import)\s+credassure\.(?:engines|datagen)""", re.M
    )
    for path in GOLD_SRC.glob("*.py"):
        assert not forbidden.search(path.read_text(encoding="utf-8")), path
