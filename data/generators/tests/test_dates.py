"""KR-04 date filter: extracted effective dates, needs_date, review sample (ADR 0019)."""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from credassure.datagen.dates import apply_dates, candidate_date, review_markdown


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("RBI/2025-26/170 dated 28.11.2025", date(2025, 11, 28)),
        ("Circular No. 261/2025-26 dated 12/10/2026", date(2026, 10, 12)),
        ("Notification issued on 2025-03-21", date(2025, 3, 21)),
        ("with effect from 1st April, 2025", date(2025, 4, 1)),
        ("Press Release: October 7, 2026", date(2026, 10, 7)),
        ("Date: 15 Sept 2026", date(2026, 9, 15)),
        ("w.e.f. 22-09-2025", date(2025, 9, 22)),
        ("परिपत्र संख्या 247/2024-25   28 फरवरी 2025", date(2025, 2, 28)),
        ("फिविी 10, 2026", date(2026, 2, 10)),  # garbled text layer of फरवरी
        ("01 अगस्त 2024", date(2024, 8, 1)),
    ],
)
def test_KR04_candidate_date_reads_indian_formats(text: str, expected: date) -> None:
    hit = candidate_date(text)
    assert hit is not None and hit[0] == expected


def test_KR04_letterhead_then_labelled_then_plain_and_out_of_range_is_ignored() -> None:
    body = "x" * 500
    header = (
        "Circular 136 December 19, 2017 To all MLIs. " + body + " as per Circular dated 05.06.2015"
    )
    hit = candidate_date(header)
    assert hit is not None and hit[0] == date(2017, 12, 19)  # letterhead, not the cited circular
    hit = candidate_date(body + " Ref 01.01.2019 page 3. Circular dated 05.06.2024 on CGTMSE fees")
    assert hit is not None and hit[0] == date(2024, 6, 5)  # labelled beats the first plain date
    assert candidate_date("Established 1955, revised 31.02.2024") is None


def test_KR04_page_clocks_are_ignored() -> None:
    assert candidate_date("Skip to content Thursday, November 05, 2026 Rates") is None
    hit = candidate_date("Updated 05.11.2026. Notified 21.08.2026", ignore=date(2026, 11, 5))
    assert hit is not None and hit[0] == date(2026, 8, 21)


def test_KR04_undated_document_leaves_available_until_a_human_dates_it(
    tmp_path: Path, entry: Callable[..., dict[str, Any]]
) -> None:
    (tmp_path / "A.html").write_text("<p>Circular dated 05.06.2024</p>", encoding="utf-8")
    (tmp_path / "B.html").write_text("<p>No date anywhere</p>", encoding="utf-8")
    manifest = {
        "documents": [
            entry(doc_id="A", effective_from=None),
            entry(doc_id="B", effective_from=None),
        ]
    }
    lock: dict[str, dict[str, Any]] = {
        "A": {"status": "ok", "raw_file": "A.html"},
        "B": {"status": "ok_manual", "raw_file": "B.html"},
    }
    assert apply_dates(manifest, lock, tmp_path) == (1, 1, 0)
    a, b = manifest["documents"]
    assert a["effective_from"] == "2024-06-05" and a["date_source"] == "extracted"
    assert lock["B"]["status"] == "needs_date"
    b["effective_from"] = "2023-01-01"  # a person fills it in
    assert apply_dates(manifest, lock, tmp_path) == (1, 0, 1)  # A re-extracted each run
    assert lock["B"]["status"] == "ok_manual" and b["date_source"] == "human"


def test_KR04_review_sample_is_ten_percent_and_deterministic(
    entry: Callable[..., dict[str, Any]],
) -> None:
    docs = [entry(doc_id=f"D{i:02d}", date_source="extracted") for i in range(25)]
    lock = {d["doc_id"]: {"status": "ok", "date_evidence": "dated 01.01.2025"} for d in docs}
    first = review_markdown({"documents": docs}, lock)
    assert first.count("**yes**") == 3  # ceil(25 / 10)
    assert first == review_markdown({"documents": docs}, lock)
