"""P4 ladder maths (scope #63, KR-05): recall@5/MRR@10 and the dev-only threshold rule."""

import json
from dataclasses import dataclass

from credassure.evaluation import retrieval_ladder as ladder


@dataclass
class P:
    doc_id: str
    section_path: str | None = None


Q = [
    {
        "id": "A",
        "relevant_doc_ids": ["X"],
        "relevant_sections": [{"doc_id": "X", "section_path": ""}],
    },
    {
        "id": "B",
        "relevant_doc_ids": ["Y"],
        "relevant_sections": [{"doc_id": "Y", "section_path": ""}],
    },
]


def test_scope63_recall_and_mrr_hand_computed() -> None:
    ranked = {"A": [P("Z"), P("X")], "B": [P("Z")] * 6 + [P("Y")]}
    got = ladder.recall_and_mrr(ranked, Q)
    assert got == {"recall5": 1, "n": 2, "mrr10": round((1 / 2 + 1 / 7) / 2, 4)}


def test_scope63_threshold_catches_negatives_within_the_false_abstain_budget() -> None:
    pos = [0.9, 0.8, 0.7, 0.2]  # one answerable query scores low
    neg = [0.1, 0.15, 0.6]
    t, curve = ladder.choose_threshold(pos, neg, max_false=1)
    assert (
        t == 0.7
    )  # below 0.7: 1 false abstain (0.2) and all 3 negatives caught; 0.8 would be 2 false
    assert {c["threshold"] for c in curve} == {round(x, 4) for x in pos + neg}


def test_scope63_no_threshold_when_nothing_separates() -> None:
    assert ladder.choose_threshold([0.1, 0.2], [0.9], max_false=0)[0] is None


def test_scope63_dev_negatives_never_copy_a_test_set_question() -> None:
    from credassure.evaluation.gold.data import REPO

    items = (REPO / "evaluation" / "testset" / "v1" / "items.jsonl").read_text(encoding="utf-8")
    for line in ladder.DEV_NEG.read_text(encoding="utf-8").splitlines():
        assert json.loads(line)["query"] not in items


def test_scope63_report_renders_rungs_and_curve() -> None:
    data = {
        "rungs": [
            {"rung": 0, "label": "baseline", "flags": {"contextual_headers": False,
             "query_rewrite": False, "rerank": False},
             "frozen_v1.0": {"recall5": 26, "n": 40, "mrr10": 0.5},
             "dev": {"recall5": 12, "n": 20, "mrr10": 0.4}},
        ],
        "answerability": {"threshold": 0.3, "max_false_abstain": 1,
                          "curve": [{"threshold": 0.3, "false_abstain": 1, "caught": 6}]},
    }  # fmt: skip
    text = ladder.render(data)
    assert "| 0 | baseline |" in text and "26/40" in text and "Chosen: **0.3**" in text
