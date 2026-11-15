"""Blind judging pool for the KR-05 labels (E8 M1): deduplicated, shuffled, no configuration leak."""

from datetime import date
from pathlib import Path

from credassure.evaluation.retrieval_judging import COLUMNS, build_pool, write_pool
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
