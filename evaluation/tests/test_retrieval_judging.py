"""Blind judging pool for the KR-05 labels (E8 M1): deduplicated, shuffled, no configuration leak."""

import json
from datetime import date
from pathlib import Path

from credassure.evaluation.retrieval_judging import (
    COLUMNS,
    agreement_sample,
    build_pool,
    judge,
    load_judgments,
    write_pool,
)
from credassure.retrieval.search import Passage


def _p(doc_id: str, section: str, text: str) -> Passage:
    return Passage(f"{doc_id}#x", doc_id, "T", "public", section, date(2025, 1, 1), text, False)


QUERIES = [{"id": "Q01", "query": "fee?"}, {"id": "Q02", "query": "cap?"}]
HITS = {
    ("fixed512", "keyword", False): {
        "Q01": [_p("A", "1. Fee", "short")],
        "Q02": [_p("B", "", "b")],
    },
    ("section", "dense", True): {
        "Q01": [_p("A", "1.  fee", "a longer text"), _p("C", "2", "c")],
        "Q02": [_p("A", "1. Fee", "a")],
    },
}


def test_KR05_pool_dedupes_keeps_longest_and_groups_by_query() -> None:
    rows = build_pool(HITS, QUERIES, "s")
    assert [r["query_id"] for r in rows] == ["Q01", "Q01", "Q02", "Q02"]
    assert [r["item_id"] for r in rows] == ["J0001", "J0002", "J0003", "J0004"]
    a = next(r for r in rows if r["query_id"] == "Q01" and r["doc_id"] == "A")
    assert a["passage"] == "a longer text"  # spacing/case variants of one section merge


def test_KR05_pool_is_blind_and_deterministic(tmp_path: Path) -> None:
    rows = build_pool(HITS, QUERIES, "s")
    assert rows == build_pool(HITS, QUERIES, "s")
    write_pool(rows, tmp_path)
    sheet = (tmp_path / "judging_sheet.csv").read_text(encoding="utf-8")
    assert sheet.splitlines()[0] == ",".join(COLUMNS)
    for leak in ("fixed512", "keyword", "dense", "rerank", "rank"):
        assert leak not in sheet


def test_KR05_pool_takes_top5_only() -> None:
    deep = [_p("A", "1", "a")] * 5 + [_p("Z", "9", "rank six")]
    rows = build_pool({("fixed512", "keyword", False): {"Q01": deep, "Q02": []}}, QUERIES, "s")
    assert [r["doc_id"] for r in rows] == ["A"]


ITEMS = [
    {
        "item_id": f"J{i:04d}",
        "query_id": "Q01",
        "query": "fee?",
        "doc_id": "A",
        "title": "T",
        "section_path": "1",
        "passage": "x" * 2000,
    }
    for i in range(1, 6)
]


def _run(out: Path, keys: str) -> list[str]:
    shown: list[str] = []
    it = iter(keys)
    judge(ITEMS, out, "pritish", lambda: next(it), shown.append, "CRITERIA")
    return shown


def test_KR05_judge_saves_each_answer_back_overrides_and_resumes(tmp_path: Path) -> None:
    out = tmp_path / "judgments_pritish.jsonl"
    shown = _run(out, "21b0q")  # J1=2, J2=1, back to J2, J2=0, quit on J3
    recs = [json.loads(line) for line in out.read_text().splitlines()]
    assert [r["label"] for r in recs] == [2, 1, 0]
    assert {r["judge"] for r in recs} == {"pritish"} and all(r["ts"] for r in recs)
    assert load_judgments(out) == {"J0001": 2, "J0002": 0}
    assert "(your earlier answer: 1)" in shown[3]  # J1, J2, J3, back to J2
    assert "item 3 of 5" in _run(out, "q")[0]  # resumes at the first unanswered item


def test_KR05_judge_screen_is_blind_and_capped(tmp_path: Path) -> None:
    shown = _run(tmp_path / "j.jsonl", "scq")
    assert "item 2 of 5" in shown[1] and "CRITERIA" in shown[2]  # s skips, c shows criteria
    assert "x" * 1200 in shown[0] and "x" * 1201 not in shown[0]
    for leak in ("fixed512", "keyword", "dense", "rerank", "rank"):
        assert leak not in shown[0]


def test_KR05_agreement_sample_is_seeded_quarter() -> None:
    items = [{"item_id": f"J{i:04d}"} for i in range(1, 101)]
    a = agreement_sample(items, "20261026", 0.25)
    assert len(a) == 25 and a == agreement_sample(items, "20261026", 0.25)
    assert a != agreement_sample(items, "other", 0.25)
