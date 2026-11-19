"""P11 SOURCE_PRIORITY: a stable reorder of the same passages by kind of source (synthetic rows)."""

from credassure.retrieval.source_priority import prioritise, tier


def _p(doc_id: str, title: str, collection: str = "public") -> dict[str, str]:
    return {"doc_id": doc_id, "title": title, "collection": collection}


def test_P11_tiers_by_kind_of_source() -> None:
    assert tier(_p("R-X-1", "The Example Development Act, 2006")) == 0
    assert tier(_p("R-X-2", "Master Direction - Lending to Example Sector")) == 0
    assert tier(_p("R-X-3", "Notification No. 1/2026-Central Tax (Rate)")) == 0
    assert tier(_p("R-X-4", "SCHEME DOCUMENT")) == 0
    assert tier(_p("POL-X-v1", "Approval matrix", "policy")) == 0
    assert tier(_p("KFS-X", "Key Facts Statement", "kfs")) == 0
    assert tier(_p("R-X-5", "RBI FAQs - Example")) == 1
    assert tier(_p("FAQ-001", "Who signs off a proposal?", "policy")) == 1
    assert tier(_p("R-X-6", "Bank - service charges")) == 1
    assert tier(_p("R-SANSAD-001", "Rajya Sabha Unstarred Q. 1 (2026): Payments")) == 2
    assert tier(_p("R-X-7", "Lok Sabha Starred Q. 9: credit")) == 2
    assert tier(_p("R-JUD-001", "A v. B (Supreme Court, 2022)")) == 2
    # an "Act" mentioned inside a parliamentary answer's title is still a secondary account
    assert tier(_p("R-SANSAD-002", "Rajya Sabha Q. 5: amendments to the Example Act")) == 2


def test_P11_same_passages_stable_within_a_tier() -> None:
    hits = [
        _p("R-X-5", "RBI FAQs - Example"),
        _p("R-SANSAD-001", "Rajya Sabha Unstarred Q. 1"),
        _p("R-X-2", "Master Direction - Example"),
        _p("R-X-6", "Bank - service charges"),
        _p("R-X-1", "The Example Act, 2006"),
    ]
    out = prioritise(hits)
    assert sorted(map(id, out)) == sorted(map(id, hits))  # nothing added or removed
    assert [h["doc_id"] for h in out] == ["R-X-2", "R-X-1", "R-X-5", "R-X-6", "R-SANSAD-001"]
    assert prioritise([]) == []
