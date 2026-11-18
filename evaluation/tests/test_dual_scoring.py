"""P5.2 dual scoring (ADR 0032 §4, scope #64): strict = the frozen citation scorer; supported =
valid, current, allowed citations that judge J1 says support the answer."""

from typing import Any

from credassure.evaluation import dual_scoring as ds

ITEM: dict[str, Any] = {
    "input": {"question": "How is the AGF charged?"},
    "gold": {
        "relevant_doc_ids": ["R-CG-02"],
        "key_facts": ["guaranteed amount"],
        "must_not_cite": ["R-OLD"],
    },
}
KNOWN = {"R-CG-02", "R-CG-01", "R-OLD", "R-FUTURE"}
CURRENT = {"R-CG-02", "R-CG-01"}


def _score(answer: dict[str, Any], verdict: bool | None = True) -> ds.Dual:
    calls: list[tuple[str, str, list[str]]] = []

    def judge(q: str, a: str, p: Any) -> bool:
        calls.append((q, a, list(p)))
        return bool(verdict)

    return ds.score(
        ITEM,
        answer,
        ["passage text"],
        known=KNOWN,
        current=CURRENT,
        judge=None if verdict is None else judge,
    )


def test_P5_strict_pass_is_supported_without_the_judge() -> None:
    d = _score({"answer": "On the guaranteed amount.", "citations": ["R-CG-02"]})
    assert (d.strict, d.supported, d.judged) == (True, True, False)


def test_P5_other_current_document_counts_only_when_j1_supports_it() -> None:
    a = {"answer": "Fee is 0.85% for that slab.", "citations": ["R-CG-01"]}
    assert (_score(a, True).strict, _score(a, True).supported, _score(a, True).judged) == (
        False,
        True,
        True,
    )
    assert _score(a, False).supported is False
    assert _score(a, None).supported is False  # no judge, no supported score


def test_P5_unknown_superseded_not_current_or_uncited_is_never_supported() -> None:
    for cites in (["R-NOPE"], ["R-OLD"], ["R-FUTURE"], []):
        d = _score({"answer": "Some claim.", "citations": cites})
        assert (d.supported, d.judged) == (False, False), cites


def test_P5_abstention_scores_the_same_both_ways() -> None:
    d = _score({"answer": "I can't verify that from the available sources.", "citations": []})
    assert (d.strict, d.supported, d.judged) == (False, False, False)


def test_P5_llm_judge_fails_closed_on_garbage() -> None:
    assert ds.llm_judge(lambda p: '{"verdict": "SUPPORTED"}')("q", "a", ["p"]) is True
    assert ds.llm_judge(lambda p: "sure, supported")("q", "a", ["p"]) is False
    assert ds.llm_judge(lambda p: '{"verdict": "NOT_SUPPORTED"}')("q", "a", ["p"]) is False


def test_P5_human_sample_has_every_supported_only_row_plus_a_fifth_of_the_rest() -> None:
    rows = [{"id": f"T{i}", "judged": True, "supported": i < 3, "strict": False} for i in range(13)]
    rows.append({"id": "S", "judged": False, "supported": True, "strict": True})
    picked = [r["id"] for r in ds.human_sample(rows)]
    assert picked[:3] == ["T0", "T1", "T2"] and len(picked) == 3 + 2  # 20% of the 10 others
    assert picked == [r["id"] for r in ds.human_sample(rows)]  # seeded


def test_P5_current_documents_drop_superseded_and_future_ones() -> None:
    current = ds.current_doc_ids()
    assert "R-RBI-02" in current
    assert "R-RBI-12" not in current  # KFS circular superseded by R-RBI-02 (ADR 0026)
