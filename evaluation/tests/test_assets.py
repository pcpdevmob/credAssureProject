"""Phase 3 assets: test set counts and determinism, retrieval labels, scorers, freeze, baseline (no network)."""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from credassure.evaluation import (
    build_assets,
    build_testset,
    check_corpus_refs,
    freeze,
    record,
    scorers,
)
from credassure.evaluation.baseline import run as baseline_run
from credassure.evaluation.baseline.client import InfraError
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


# Owner of the agent each category grades (BRD §5.2; owners set 25 Nov).
CATEGORY_OWNER = {
    "regulatory": "Adesh",  # copilot
    "onboarding": "Mousita",
    "cashflow": "Suresh",
    "offers": "Pritish",
    "negotiation": "Pritish",
    "routing": "Abhishek",  # supervisor
    "injection": "Adesh",
    "refusal": "Adesh",
    "isolation": "Abhishek",  # gateway case scoping
    "e2e": "Abhishek",
}
# Disclosed exception (CONTRIBUTIONS.md): the 3 isolation items were written on 15 Nov, before their author was named
# owner of the gateway on 25 Nov. They are decided by code (403/404) and the frozen set is never re-authored.
OWN_GOLD_EXCEPTIONS = {"isolation"}


def test_BRD5_nobody_writes_gold_for_their_own_agent() -> None:
    assert set(build_testset.AUTHOR) == set(CATEGORY_OWNER)
    own = {c for c in CATEGORY_OWNER if build_testset.AUTHOR[c] == CATEGORY_OWNER[c]}
    assert own == OWN_GOLD_EXCEPTIONS
    assert all(i["author"] == build_testset.AUTHOR[i["category"]] for i in ITEMS)


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


def test_KR05_committed_queries_match_the_builder() -> None:
    committed = (REPO / "evaluation/retrieval/v1/queries.jsonl").read_text(encoding="utf-8")
    rebuilt = "".join(
        json.dumps(q, sort_keys=True, ensure_ascii=False) + "\n" for q in build_assets.queries()
    )
    assert committed == rebuilt


def test_KR05_every_label_names_a_section_or_is_an_exact_whole_document() -> None:
    for q in QUERIES:
        assert {s["doc_id"] for s in q["relevant_sections"]} == set(q["relevant_doc_ids"]), q["id"]
        for s in q["relevant_sections"]:
            assert s["section_path"] or s.get("exact") is True, (q["id"], s)


def test_KR05_a_document_without_a_label_fails_the_builder() -> None:
    with pytest.raises(ValueError, match="no section label"):
        build_assets.labels("Q01", "R-NOT-LABELLED")


def test_BRD13_regulatory_gold_has_evidence_from_its_cited_documents() -> None:
    for item in ITEMS:
        gold = item["gold"]
        if item["category"] == "regulatory" and not gold.get("abstain"):
            assert gold["key_facts"] and gold["evidence"], item["id"]
            assert {e["doc_id"] for e in gold["evidence"]} <= set(gold["relevant_doc_ids"])


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
        scorers.citation(cite, {"answer": "x", "citations": []}, known)["failure_class"]
        == "no_citation"
    )
    wrong = {"answer": "x", "citations": ["R-CG-02"]}
    other = cite | {"relevant_doc_ids": ["R-CG-05"]}
    assert scorers.citation(other, wrong, known)["failure_class"] == "wrong_citation"
    assert scorers.BRD_CLASS["no_citation"] == scorers.BRD_CLASS["wrong_citation"] == "search_miss"
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


def test_G1_frozen_assets_have_not_changed() -> None:
    assert freeze.verify() == []  # no manifest yet → []; after /freeze-g1 any drift fails here


def test_G1_freeze_verify_detects_a_changed_asset(tmp_path: Path, monkeypatch: Any) -> None:
    for asset in freeze.ASSETS:
        (tmp_path / asset).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / asset).write_bytes(b"frozen\n")
    monkeypatch.setattr(freeze, "REPO", tmp_path)
    monkeypatch.setattr(freeze, "MANIFEST", tmp_path / "FROZEN.sha256")
    freeze.MANIFEST.write_text(freeze.digests(), encoding="utf-8")
    assert freeze.verify() == []
    (tmp_path / freeze.ASSETS[0]).write_bytes(b"frozen!\n")
    assert freeze.verify() == [freeze.ASSETS[0]]


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


@pytest.mark.skipif(
    "R-CG-02" not in check_corpus_refs.Corpus().texts(),
    reason="corpus text not extracted locally (data/corpus is gitignored; fresh clone or CI)",
)
def test_G1_readiness_lists_items_without_an_available_document() -> None:
    blocked = freeze.readiness()
    assert all(": " in b for b in blocked)  # reported, and --write refuses while any remain
    assert not any(b.startswith("T001:") for b in blocked)  # R-CG-02 is downloaded


def test_KR04_corpus_guard_unknown_awaiting_key_fact_and_strict(tmp_path: Path) -> None:
    (tmp_path / "text").mkdir()
    (tmp_path / "syn" / "policies").mkdir(parents=True)
    (tmp_path / "manifest.yaml").write_text(
        "documents:\n- doc_id: A\n- doc_id: B\n- doc_id: C\n", encoding="utf-8"
    )
    (tmp_path / "lock.json").write_text(
        json.dumps(
            {"A": {"status": "ok"}, "B": {"status": "pending_manual"}, "C": {"status": "ok"}}
        ),
        encoding="utf-8",
    )
    (tmp_path / "text" / "A.txt").write_text("Fee on the  Guaranteed\namount.", encoding="utf-8")
    corpus = check_corpus_refs.Corpus(
        tmp_path / "manifest.yaml", tmp_path / "lock.json", tmp_path / "text", tmp_path / "syn"
    )  # C is "ok" but has no extracted text, so it is not available
    rows = [
        {
            "id": "T1",
            "category": "regulatory",
            "gold": {"relevant_doc_ids": ["A"], "key_facts": ["guaranteed amount"]},
        },
        {
            "id": "T2",
            "category": "regulatory",
            "gold": {"relevant_doc_ids": ["A"], "key_facts": ["0.85"]},
        },
        {"id": "Q1", "relevant_doc_ids": ["A"], "must_not_cite": ["B", "C"]},
        {"id": "Q2", "relevant_doc_ids": ["Z"]},
    ]
    report = check_corpus_refs.check(corpus, rows)
    assert report.failures == [
        "T2: key fact '0.85' not found in A",
        "Q2: not in manifest: Z",
    ]
    assert report.awaiting == ["Q1: awaiting corpus: B, C"]
    strict = check_corpus_refs.check(corpus, rows, strict=True)
    assert "Q1: awaiting corpus: B, C" in strict.failures and not strict.awaiting


def test_KR04_corpus_guard_evidence_and_supersession_in_freeze_mode(tmp_path: Path) -> None:
    (tmp_path / "text").mkdir()
    (tmp_path / "syn").mkdir()
    (tmp_path / "manifest.yaml").write_text(
        "documents:\n"
        "- {doc_id: NEW, effective_from: '2025-01-01'}\n"
        "- {doc_id: OLD, superseded_by: NEW}\n"
        "- {doc_id: FUTURE, effective_from: '2027-01-01'}\n"
        "- {doc_id: PRE, superseded_by: FUTURE}\n"
        "- {doc_id: R-RBI-01}\n"
        "- {doc_id: CIRC, superseded_by: R-RBI-01}\n",
        encoding="utf-8",
    )
    ids = ["NEW", "OLD", "FUTURE", "PRE", "R-RBI-01", "CIRC"]
    (tmp_path / "lock.json").write_text(json.dumps({d: {"status": "ok"} for d in ids}))
    for d in ids:
        (tmp_path / "text" / f"{d}.txt").write_text(f"{d} text: fee is 0.85 per cent.")
    corpus = check_corpus_refs.Corpus(
        tmp_path / "manifest.yaml", tmp_path / "lock.json", tmp_path / "text", tmp_path / "syn"
    )

    def reg(i: str, rel: list[str], bad: list[str], ev: list[dict[str, str]]) -> dict[str, Any]:
        gold = {"relevant_doc_ids": rel, "must_not_cite": bad, "key_facts": [], "evidence": ev}
        return {"id": i, "category": "regulatory", "gold": gold}

    rows = [
        reg("T1", ["NEW"], ["OLD"], [{"doc_id": "NEW", "quote": "fee is 0.85  per cent"}]),
        reg("T2", ["NEW"], ["OLD"], [{"doc_id": "NEW", "quote": "fee is 1.00 per cent"}]),
        reg("T3", ["NEW"], ["OLD"], [{"doc_id": "OLD", "quote": "fee is 0.85 per cent"}]),
        reg("T4", ["OLD"], [], []),  # superseded, replacement in force
        reg("T5", ["NEW"], [], []),  # predecessor OLD not excluded
        reg("T6", ["PRE"], [], []),  # replacement not yet in force: still current
        reg("T7", ["R-RBI-01"], [], []),  # withdrawal notice: its circulars are not versions
    ]
    lenient = check_corpus_refs.check(corpus, rows)
    assert lenient.failures == [
        "T2: evidence 'fee is 1.00 per cent' not found in NEW",
        "T3: evidence from uncited OLD",
    ]
    assert check_corpus_refs.check(corpus, rows, strict=True).failures == [
        "T2: evidence 'fee is 1.00 per cent' not found in NEW",
        "T3: evidence from uncited OLD",
        "T4: relevant OLD is superseded by NEW (move to must_not_cite)",
        "T5: predecessor OLD of NEW not in must_not_cite",
    ]


class DownChat:
    """Endpoint that fails twice on every call (what the client raises after its one retry)."""

    model, endpoint = "llama3.1:8b", "http://localhost:11434/v1"

    def complete(
        self, messages: list[dict[str, str]], temperature: float, seed: int
    ) -> tuple[str, int]:
        raise InfraError("ReadTimeout")


def test_BRD12_infra_errors_are_excluded_from_accuracy_and_counted(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.delenv("EVAL_NUM_CTX", raising=False)
    items = ITEMS[:2]
    down = baseline_run.evaluate(
        "s2", items, DownChat(), tmp_path
    )  # any of 5 samples down → item down
    up = baseline_run.evaluate("s1", items, GoldChat(items), tmp_path)
    assert [r["failure_class"] for r in down] == ["infra_error", "infra_error"]
    assert all(r["passed"] is None and r["run_kind"] == "smoke_test" for r in down)
    record = json.loads((tmp_path / "record_s2.json").read_text(encoding="utf-8"))
    assert record["context_length"] is None and record["run_kind"] == "smoke_test"
    text = baseline_run.summary({"s1": up, "s2": down}, record)
    assert "**2/2**" in text and "**0/0 (2 infra)**" in text and "| infra_error | | 0 | 2 |" in text


def test_scope13_run_kind_only_course_endpoint_is_graded() -> None:
    assert record.run_kind("https://course.example/v1", None) == "graded"
    assert record.run_kind("http://localhost:11434/v1", 8192) == "local_provisional"
    assert record.run_kind("http://127.0.0.1:11434/v1", None) == "smoke_test"


def test_BRD13_malformed_answers_score_as_schema_failure_never_crash() -> None:
    known = baseline_run.known_doc_ids()
    junk: list[Any] = [[{"a": 1}, {"b": 2}], {"x": 1}, "text", 3, None]
    for item in ITEMS:
        for value in junk:
            answer = {k: value for k in item["gold"]} if isinstance(item["gold"], dict) else {}
            verdict = scorers.score(item, answer, known)
            assert verdict["passed"] in (True, False), item["id"]


def test_KR05_corpus_guard_reads_amounts_written_in_words() -> None:
    """Gazette notifications spell limits out ("twenty five crore"); the guard must still match "25 crore"."""
    from credassure.evaluation.check_corpus_refs import _norm

    text = _norm(
        "the words “twenty five crore” and “one hundred crore”, “one hundred twenty five crore”"
    )
    assert _norm("25 crore") in text
    assert _norm("100 crore") in text
    assert _norm("125 crore") in text
    assert _norm("two crore and fifty lakh") == _norm("2 crore and 50 lakh")
    assert (
        _norm("Section One") == "section 1"
    )  # documented ceiling: any number word becomes a digit
