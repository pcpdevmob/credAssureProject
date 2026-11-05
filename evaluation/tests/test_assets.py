"""Phase 3 assets: test set counts and determinism, retrieval labels, scorers, freeze, baseline (no network)."""

import json
from collections import Counter
from typing import Any

from credassure.evaluation import build_assets, build_testset, freeze, scorers
from credassure.evaluation.baseline import run as baseline_run
from credassure.evaluation.baseline.strategies import parse_json, run, user_prompt
from credassure.evaluation.gold.data import REPO

ITEMS = [
    json.loads(line)
    for line in (REPO / "evaluation/testset/v1/items.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
]
QUERIES = [
    json.loads(line)
    for line in (REPO / "evaluation/retrieval/v1/queries.jsonl")
    .read_text(encoding="utf-8")
    .splitlines()
]


def test_BRD13_category_counts_are_exact() -> None:
    assert Counter(i["category"] for i in ITEMS) == build_testset.COUNTS
    assert len({i["id"] for i in ITEMS}) == 100
    assert (
        sum(i.get("subtype") == "abstention" for i in ITEMS) == 10
    )  # S23: 6 regulatory + 4 refusal


def test_BRD13_committed_items_match_the_builder() -> None:
    committed = (REPO / "evaluation/testset/v1/items.jsonl").read_text(encoding="utf-8")
    rebuilt = "".join(
        json.dumps(i, sort_keys=True, ensure_ascii=False) + "\n" for i in build_testset.build()
    )
    assert committed == rebuilt


def test_KR05_forty_queries_with_valid_labels() -> None:
    known = baseline_run.known_doc_ids()
    assert len(QUERIES) == 40
    for q in QUERIES:
        assert q["relevant_doc_ids"], q["id"]
        assert set(q["relevant_doc_ids"]) <= known and set(q["must_not_cite"]) <= known
        assert not set(q["relevant_doc_ids"]) & set(q["must_not_cite"])


def test_BRD14_VER02_redteam_and_bad_citation_fixtures() -> None:
    assert len(build_assets.redteam()) == 20
    assert len(build_assets.bad_citations()) == 12
    assert {b["expected"] for b in build_assets.bad_citations()} == {
        "VER_BAD_CITATION",
        "VER_SUPERSEDED_SOURCE",
    }


def test_WC03_CP02_scorers_money_rate_and_citation_rules() -> None:
    gold = {
        "gate": "GO",
        "recommended_amount": 14200000,
        "peak_shortfall": 16200000,
        "peak_week": 9,
    }
    assert scorers.exact_money(gold, gold | {"recommended_amount": 14200000.6})["passed"]
    assert (
        scorers.exact_money(gold, gold | {"recommended_amount": 14200002})["failure_class"]
        == "arithmetic_error"
    )
    cite = {
        "key_facts": ["outstanding"],
        "relevant_doc_ids": ["R-CG-02"],
        "must_not_cite": ["R-MSME-03"],
    }
    known = {"R-CG-02", "R-MSME-03"}
    assert scorers.citation(
        cite, {"answer": "on the outstanding amount", "citations": ["R-CG-02"]}, known
    )["passed"]
    assert (
        scorers.citation(cite, {"answer": "x", "citations": ["R-XX-9"]}, known)["failure_class"]
        == "invented_citation"
    )
    assert (
        scorers.citation(cite, {"answer": "outstanding", "citations": ["R-MSME-03"]}, known)[
            "failure_class"
        ]
        == "superseded_citation"
    )
    assert scorers.refusal({"abstain": True}, {"answer": scorers.ABSTAIN})["passed"]


def test_VER03_scorers_catch_acceptance_language_and_injection() -> None:
    gold = {"target_offer": "OF-01-A", "competing_fee_pct": 0.95, "concession_counts": True}
    bad = {
        "target_offer": "OF-01-A",
        "competing_fee_pct": 0.95,
        "concession_counts": True,
        "message": "We accept your offer.",
    }
    assert scorers.negotiation(gold, bad)["failure_class"] == "injection_followed"
    assert (
        scorers.injection({"ranking": ["B"]}, {"ranking": ["A", "B"], "injection_flagged": True})[
            "failure_class"
        ]
        == "injection_followed"
    )


def test_G1_freeze_verify_is_clean_without_a_manifest() -> None:
    assert freeze.verify() == [] or (REPO / "evaluation/FROZEN.sha256").exists()


class GoldChat:
    """Answers every item with its gold, so a perfect model scores 100/100 (checks prompts and scorers agree)."""

    model, endpoint = "gold", "fake://"

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.by_prompt = {user_prompt(i): i for i in items}

    def complete(
        self, messages: list[dict[str, str]], temperature: float, seed: int
    ) -> tuple[str, int]:
        item = next(v for k, v in self.by_prompt.items() if messages[-1]["content"].startswith(k))
        return "Working...\n" + json.dumps(_perfect(item)), 10


def _perfect(item: dict[str, Any]) -> dict[str, Any]:
    gold, cat = item["gold"], item["category"]
    if gold.get("abstain"):
        return {"refused": True, "answer": scorers.ABSTAIN}
    if cat == "regulatory":
        return {"answer": " ".join(gold["key_facts"]), "citations": gold["relevant_doc_ids"][:1]}
    if cat in {"refusal", "isolation"}:
        return {"refused": True, "answer": "I can't help with that."}
    if cat == "onboarding":
        return {"gate": gold["gate"], "failed_rules": gold["failed_rules"]}
    if cat == "cashflow" and gold["gate"] == "NEEDS_INPUT":
        return {
            "gate": "NEEDS_INPUT",
            "missing_or_conflicting": [b["field"] for b in gold["blockers"]],
        }
    if cat == "negotiation":
        return gold | {
            "message": ""
            if gold["target_offer"] is None
            else "Please consider waiving the processing fee."
        }
    if cat == "injection":
        return {"ranking": gold["ranking"], "injection_flagged": True, "answer": "Ranked on cost."}
    return dict(gold)


def test_BRD12_baseline_pipeline_scores_a_perfect_model_100(tmp_path: Any) -> None:
    chat = GoldChat(ITEMS)
    known = baseline_run.known_doc_ids()
    for strategy in ("s1", "s2", "s3"):
        failures = []
        for item in ITEMS:
            answer, _, _ = run(strategy, item, chat)
            verdict = scorers.score(item, answer, known)
            if not verdict["passed"]:
                failures.append((item["id"], verdict))
        assert failures == [], (strategy, failures[:3])


def test_BRD12_parse_json_takes_the_last_object() -> None:
    assert parse_json('think {"a": 1} then {"route": "HELD"}') == {"route": "HELD"}
    assert parse_json("no json here") is None


def test_G1_readiness_lists_items_without_an_available_document() -> None:
    blocked = freeze.readiness()
    assert all(": " in b for b in blocked)  # reported, and --write refuses while any remain
    assert not any(b.startswith("T001:") for b in blocked)  # R-CG-02 is downloaded
