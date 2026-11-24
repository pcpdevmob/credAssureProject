"""P7 (Phase 11): failure taxonomy, ablation claim rule, best baseline, J1 judge and calibration.
The harness mechanics through the API are in tests/e2e/test_eval_harness.py."""

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from credassure.evaluation import eval_report as er
from credassure.evaluation import harness, judge_j1

REG = {
    "id": "T001",
    "category": "regulatory",
    "scorer": "citation",
    "input": {"question": "Q?"},
    "gold": {
        "key_facts": ["guaranteed amount"],
        "evidence": [{"quote": "q"}],
        "relevant_doc_ids": ["R-CG-02"],
    },
}


def test_scope12_citation_miss_is_a_search_miss_unless_the_document_is_invented() -> None:
    fail = {"passed": False, "failure_class": "invented_citation"}
    assert (
        harness.brd_class(REG, fail, {"answer": "I can't verify that from the available sources."})
        == "search_miss"
    )
    assert harness.brd_class(REG, fail, {"answer": "x", "citations": ["R-CG-01"]}) == "search_miss"
    assert (
        harness.brd_class(REG, fail, {"answer": "x", "citations": ["R-MADE-UP"]}) == "hallucination"
    )
    assert (
        harness.brd_class(
            {"scorer": "exact_money"}, {"passed": False, "failure_class": "arithmetic_error"}, {}
        )
        == "reasoning_error"
    )
    assert harness.brd_class(REG, {"passed": True}, {}) is None


def test_BRD12_ablation_effect_is_claimed_only_on_two_categories_or_a_rerun() -> None:
    full = {"offers": (15, 15), "e2e": (5, 5), "cashflow": (15, 15)}
    one = {"offers": (10, 15), "e2e": (5, 5)}
    two = {"offers": (10, 15), "e2e": (3, 5)}
    assert er.ablation_effect(full, [two]) == (["offers", "e2e"], "claimed")
    assert er.ablation_effect(full, [one])[1].startswith("not claimed")
    assert er.ablation_effect(full, [one, one]) == (["offers"], "claimed")
    assert er.ablation_effect(full, [{"offers": (15, 15)}]) == ([], "no effect")


def test_BRD12_best_baseline_is_the_strategy_with_most_passes(tmp_path: Path) -> None:
    for name, passes in (("s1_structured", 3), ("s2_cot_vote", 5), ("s3_decompose", 4)):
        rows = [{"id": f"T{i}", "category": "offers", "passed": i < passes} for i in range(10)]
        (tmp_path / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    best = er.baseline_best(tmp_path)
    assert best is not None and best[0] == "s2_cot_vote"
    assert er.baseline_best(tmp_path / "missing") is None


def test_ADR0014_j1_fails_closed_and_kappa_decides_who_scores(
    tmp_path: Path, monkeypatch: Any
) -> None:
    assert judge_j1.judge_one(lambda p: '{"verdict": "CORRECT"}', REG, "a") is True
    assert judge_j1.judge_one(lambda p: "looks right", REG, "a") is False
    monkeypatch.setattr(judge_j1, "load", lambda _p: [REG | {"id": f"T{i:03d}"} for i in range(10)])
    rows = [
        {"id": f"T{i:03d}", "category": "regulatory", "answer": {"answer": f"ans {i}"}}
        for i in range(10)
    ]
    (tmp_path / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    judged = judge_j1.judge_run(tmp_path, lambda p: '{"verdict": "CORRECT"}')
    assert len(judged) == 10
    with (tmp_path / "j1-human-sample.csv").open() as f:
        sample = list(csv.DictReader(f))
    assert len(sample) == 2 and "j1" not in sample[0]  # 20%, blind to J1
    for r in sample:
        r["human_correct (y/n)"] = "y"
    with (tmp_path / "j1-human-sample.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sample[0]))
        w.writeheader()
        w.writerows(sample)
    cal = judge_j1.calibrate(tmp_path)
    assert (cal["n"], cal["agreement"], cal["free_text_scored_by"]) == (2, 1.0, "J1")


def test_D4_sample_all_exports_every_judged_answer_and_reports_the_human_score(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Human review D4: 20% of ~15 answers is too few for kappa; people label every one."""
    monkeypatch.setattr(judge_j1, "load", lambda _p: [REG | {"id": f"T{i:03d}"} for i in range(7)])
    rows = [
        {"id": f"T{i:03d}", "category": "regulatory", "answer": {"answer": f"ans {i}"}}
        for i in range(7)
    ]
    (tmp_path / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    verdicts = iter(["CORRECT"] * 4 + ["INCORRECT"] * 3)
    judge_j1.judge_run(tmp_path, lambda p: json.dumps({"verdict": next(verdicts)}), fraction=1.0)
    with (tmp_path / "j1-human-sample.csv").open() as f:
        sample = list(csv.DictReader(f))
    assert [r["id"] for r in sample] == [f"T{i:03d}" for i in range(7)]  # all, in run order
    assert all("j1" not in r for r in sample)  # still blind to J1
    for i, r in enumerate(sample):  # humans agree on 6 of 7: T003 is wrong for them
        r["human_correct (y/n)"] = "y" if i < 3 else "n"
    with (tmp_path / "j1-human-sample.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sample[0]))
        w.writeheader()
        w.writerows(sample)
    cal = judge_j1.calibrate(tmp_path)
    assert (cal["n"], cal["judged"], cal["pending"]) == (7, 7, 0)
    assert (cal["human_correct"], cal["j1_correct"]) == (3, 4)
    assert cal["agreement"] == round(6 / 7, 3) and cal["kappa"] >= 0.7
    line = er._human_score(cal)
    assert "every judged answer" in line and "humans 3/7" in line and "J1 4/7" in line
    assert er._human_score({"n": 2, "agreement": 1.0}) == ""  # older calibration files


def test_D4_sample_option_is_a_fraction_or_all(tmp_path: Path) -> None:
    for bad in ("0", "1.5", "-0.2"):
        with pytest.raises(SystemExit):
            judge_j1.main(["judge", "--run", str(tmp_path), "--sample", bad])
