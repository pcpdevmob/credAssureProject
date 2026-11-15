"""Blind judging pool for the KR-05 labels (E8 M1): deduplicated, shuffled, no configuration leak."""

import json
from datetime import date
from pathlib import Path

import pytest

from credassure.evaluation.retrieval_eval import is_relevant
from credassure.evaluation.retrieval_judging import (
    COLUMNS,
    build_pool,
    cohen_kappa,
    disputed,
    judge,
    kappa_main,
    kappa_stats,
    load_judgments,
    self_consistency,
    stratified_sample,
    widen,
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


def test_KR05_self_consistency_is_binary_on_grade_2() -> None:
    grades = {"J1": 2, "J2": 1, "J3": 0, "C1": 2, "C2": 0, "C3": 2}
    assert self_consistency(grades, {"C1": "J1", "C2": "J2", "C3": "J3"}) == (2, 1, 3)


LQ = [
    {
        "id": "Q01",
        "relevant_doc_ids": ["A"],
        "relevant_sections": [{"doc_id": "A", "section_path": "1. Fee"}],
    }
]
POOL = [
    {"item_id": "J0001", "query_id": "Q01", "doc_id": "A", "section_path": "1. Fee > (a)"},
    {"item_id": "J0002", "query_id": "Q01", "doc_id": "B", "section_path": "2. Basis"},
    {"item_id": "J0003", "query_id": "Q01", "doc_id": "C", "section_path": ""},
    {"item_id": "J0004", "query_id": "Q01", "doc_id": "D", "section_path": "9"},
]
GRADES = {"J0001": 0, "J0002": 2, "J0003": 2, "J0004": 1}


def test_KR05_silver_widens_never_shrinks_and_preamble_is_exact() -> None:
    strict, added = widen(LQ, POOL, GRADES, 2)
    q = strict[0]
    assert q["relevant_doc_ids"] == ["A", "B", "C"] and LQ[0]["relevant_doc_ids"] == ["A"]
    assert [r["item_id"] for r in added["Q01"]] == ["J0002", "J0003"]
    assert {"doc_id": "A", "section_path": "1. Fee"} in q["relevant_sections"]  # v1.0 kept
    assert is_relevant(_p("C", "", "t"), q, section=True)
    assert not is_relevant(_p("C", "3. Other", "t"), q, section=True)  # exact: not whole document
    lenient, _ = widen(LQ, POOL, GRADES, 1)
    assert lenient[0]["relevant_doc_ids"] == ["A", "B", "C", "D"]
    assert [r["item_id"] for r in disputed(LQ, POOL, GRADES)] == ["J0001"]


def test_KR05_human_sample_is_seeded_stratified_and_blind() -> None:
    pool = [{"item_id": f"J{i:04d}"} for i in range(1, 101)]
    grades = {r["item_id"]: (2 if i < 20 else 1 if i < 30 else 0) for i, r in enumerate(pool)}
    ids = stratified_sample(pool, grades, "20261026", 0.25)
    assert len(ids) == 25 and ids == stratified_sample(pool, grades, "20261026", 0.25)
    assert sorted(ids) == ids  # pool order, not grade order
    assert [sum(grades[i] == g for i in ids) for g in (2, 1, 0)] == [5, 2, 18]  # 2.5 → 2 or 3
    assert ids != stratified_sample(pool, grades, "other", 0.25)


def test_KR05_cohen_kappa() -> None:
    assert cohen_kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert cohen_kappa([True, True, False, False], [True, False, True, False]) == 0.0
    assert (
        round(cohen_kappa([True] * 3 + [False] * 7, [True] * 2 + [False] * 8), 3) == 0.737
    )  # po 0.9, pe 0.62


def test_KR05_weighted_kappa_uniform_weights_equal_plain() -> None:
    a, b = [True] * 3 + [False] * 7, [True] * 2 + [False] * 8
    assert cohen_kappa(a, b, [2.5] * 10) == pytest.approx(cohen_kappa(a, b))


def test_KR05_weighted_kappa_reweights_to_pool_grade_mix() -> None:
    # 2 grade-2 items (pool 2, weight 1) agree R/R; 2 grade-0 items (pool 8, weight 4): one N/N,
    # one silver N vs human R. Weighted: po 6/10, pa 0.2, pb 0.6, pe 0.44 -> (0.6-0.44)/0.56.
    silver = {"A": 2, "B": 2, "C": 0, "D": 0}
    human = {"A": 2, "B": 2, "C": 0, "D": 2}
    pool = {"A": 2, "B": 2, **{f"P{i}": 0 for i in range(6)}, "C": 0, "D": 0}
    plain, agreement, weighted = kappa_stats(["A", "B", "C", "D"], silver, human, pool)
    assert plain == pytest.approx(0.5)  # po .75, pe .5
    assert agreement == pytest.approx(0.6)
    assert weighted == pytest.approx(0.16 / 0.56)


def test_KR05_kappa_verdict_uses_weighted_kappa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Plain kappa 0.75 (>= 0.7) but weighted 0.353 (po 34/44, pe 1256/1936): the grade-0 stratum is 10x larger in the pool.
    from credassure.evaluation import retrieval_judging as rj

    sample = [f"S2-{i}" for i in range(4)] + [f"S0-{i}" for i in range(4)]
    pool = [{"item_id": i} for i in sample] + [{"item_id": f"P0-{i}"} for i in range(36)]
    silver = {i: 2 if i.startswith("S2") else 0 for i in sample} | {f"P0-{i}": 0 for i in range(36)}
    human = {i: 2 if i.startswith("S2") or i == "S0-3" else 0 for i in sample}

    def jsonl(name: str, rows: list[dict[str, object]]) -> None:
        (tmp_path / name).write_text("".join(json.dumps(r) + "\n" for r in rows))

    jsonl("pool.jsonl", pool)
    jsonl("silver.jsonl", [{"item_id": k, "judgment": v} for k, v in silver.items()])
    jsonl("judgments_ann.jsonl", [{"item_id": k, "label": v} for k, v in human.items()])
    (tmp_path / "sample.json").write_text(json.dumps({"item_ids": sample}))
    monkeypatch.setattr(rj, "JUDGING", tmp_path)
    monkeypatch.setattr(rj, "SILVER", tmp_path / "silver.jsonl")
    monkeypatch.setattr(rj, "SAMPLE", tmp_path / "sample.json")
    assert kappa_main(["--judge", "ann"]) == 0
    out = capsys.readouterr().out
    assert "plain κ = 0.750" in out and "weighted κ = 0.353" in out
    assert "full human judging" in out
