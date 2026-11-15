"""KR-04 / KR-05 scoring rules of the retrieval eval (no index, no network)."""

from datetime import date
from typing import Any

import pytest

from credassure.evaluation.retrieval_eval import (
    Row,
    exit_code,
    is_relevant,
    isolation,
    kr04_violation,
    report,
    section_match,
)
from credassure.retrieval.search import Passage

Q: dict[str, Any] = {
    "id": "Q1",
    "query": "q",
    "filters": {"as_of": "2026-11-15", "home_state": "IN-MH", "lender_type": "commercial_bank"},
    "relevant_doc_ids": ["R-CG-02"],
    "relevant_sections": [{"doc_id": "R-CG-02", "section_path": "Annual Guarantee Fee"}],
    "must_not_cite": ["R-OLD"],
}
DOC = {
    "doc_id": "D",
    "effective_from": "2025-04-01",
    "superseded_by": None,
    "jurisdiction": "IN",
    "applies_to": "all",
    "case_id": None,
    "tenant_id": None,
    "legal_basis": "L4",
}


def _p(doc_id: str, section: str | None) -> Passage:
    return Passage(
        f"{doc_id}#section#0", doc_id, "t", "public", section, date(2025, 4, 1), "x", False
    )


def test_KR05_relevance_is_document_plus_section_prefix() -> None:
    assert is_relevant(_p("R-CG-02", "Annual Guarantee Fee > 2. Basis"), Q, section=True)
    assert not is_relevant(_p("R-CG-02", "Contact us"), Q, section=True)
    assert is_relevant(_p("R-CG-02", "Contact us"), Q, section=False)
    assert not is_relevant(_p("R-CG-01", "Annual Guarantee Fee"), Q, section=True)


def test_KR05_section_label_matches_a_segment_and_ignores_spacing() -> None:
    assert section_match("[TO BE PUBLISHED IN THE GAZZETE] > 15 Heading  9971", "15 Heading 9971")
    assert section_match("Annex XIII- Format of KFS", "Annex XIII")
    assert section_match(None, "")  # "" labels the whole document
    assert not section_match("Annex XII", "Annex XIII")
    assert not section_match("Chapter I > 2. Scope", "Scope")


@pytest.mark.parametrize(
    ("change", "why"),
    [
        ({"doc_id": "R-OLD"}, "must_not_cite"),
        ({"effective_from": "2027-01-01"}, "not_yet_in_force"),
        ({"effective_from": None}, "not_yet_in_force"),
        ({"superseded_by": "R-NEW"}, "superseded"),
        ({"jurisdiction": "IN-GJ"}, "other_state"),
        ({"applies_to": "nbfc"}, "other_lender_type"),
        ({"case_id": "CA-2"}, "other_case"),
    ],
)
def test_KR04_each_distractor_kind_is_named(change: dict[str, Any], why: str) -> None:
    assert kr04_violation(DOC | change, Q) == why


def test_KR04_current_home_state_document_passes() -> None:
    assert kr04_violation(DOC | {"jurisdiction": "IN-MH"}, Q) is None


def test_KR05_report_marks_target_open_and_lists_awaiting() -> None:
    row = Row("section", "hybrid", False, {"Q1"}, {"Q1"}, {"Q1"})
    text = report(
        [row],
        [],
        [Q],
        {"D": DOC},
        ["Q9: awaiting corpus: R-X"],
        {"date": "d", "as_of": "2026-11-15"},
        "n",
    )
    assert "1/1" in text and "OPEN" in text and "Q9: awaiting corpus: R-X" in text
    assert "Violations: **0**" in text


def test_KR04_superseded_only_once_the_replacement_is_in_force() -> None:
    old = DOC | {"superseded_by": "NEW"}
    assert (
        kr04_violation(old, Q, {"NEW": DOC | {"doc_id": "NEW", "effective_from": "2027-01-01"}})
        is None
    )
    assert kr04_violation(old, Q, {"NEW": DOC | {"doc_id": "NEW"}}) == "superseded"
    assert kr04_violation(old, Q, {}) == "superseded"  # unknown replacement: fail closed


def test_SUP08_kfs_needs_the_same_tenant_and_case() -> None:
    kfs = DOC | {"case_id": "CA-2026-0001", "tenant_id": "demo"}
    mine = Q | {"filters": Q["filters"] | {"case_id": "CA-2026-0001", "tenant_id": "demo"}}
    other = Q | {"filters": Q["filters"] | {"case_id": "CA-2026-0001", "tenant_id": "default"}}
    assert kr04_violation(kfs, mine) is None
    assert kr04_violation(kfs, other) == "other_case"


def test_SUP08_live_isolation_needs_own_kfs_and_no_other_case() -> None:
    mine = DOC | {"doc_id": "K1", "case_id": "CA-1", "tenant_id": "demo"}
    theirs = DOC | {"doc_id": "K2", "case_id": "CA-2", "tenant_id": "demo"}
    docs = {"D": DOC, "K1": mine, "K2": theirs}
    check = Q | {"id": "ISO1", "filters": Q["filters"] | {"case_id": "CA-1", "tenant_id": "demo"}}
    hits = {
        ("section", "hybrid", False): {"ISO1": [_p("D", None), _p("K1", None)]},  # pass
        ("section", "dense", False): {"ISO1": [_p("D", None)]},  # own KFS missing
        ("section", "keyword", True): {"ISO1": [_p("K1", None), _p("K2", None)]},  # leak
    }
    leaks, misses = isolation(hits, [check], docs)
    assert leaks == ["ISO1 section/keyword/rerank=on: K2 (other_case)"]
    assert misses == ["ISO1 section/dense/rerank=off: no CA-1 KFS in the top 10"]


def test_KR04_violation_fails_the_command() -> None:
    assert exit_code(["Q1 section/dense: R-OLD (superseded)"], []) == 1


def test_SUP08_isolation_leak_fails_the_command() -> None:
    assert exit_code([], ["ISO1 section/keyword/rerank=on: K2 (other_case)"]) == 1


def test_SUP08_own_kfs_recall_miss_is_reported_but_passes() -> None:
    # The known ISO3 semantic/dense/rerank=off miss: a recall miss, not a leak (E8 addendum).
    miss = "ISO3 semantic/dense/rerank=off: no CA-2026-0013 KFS in the top 10"
    check = {"id": "ISO3", "query": "q", "filters": {"case_id": "CA-2026-0013"}}
    row = Row("section", "hybrid", False, {"Q1"}, {"Q1"}, {"Q1"})
    meta = {"date": "d", "as_of": "2026-11-15"}
    text = report([row], [], [Q], {"R-CG-02": DOC}, [], meta, "", [check], [], [miss])
    assert "RECALL MISS" in text and miss in text
    assert exit_code([], []) == 0
