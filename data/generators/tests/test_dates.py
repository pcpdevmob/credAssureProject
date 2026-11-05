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
    b["effective_from"], b["date_source"] = "2023-01-01", "human"  # a person fills it in
    assert apply_dates(manifest, lock, tmp_path) == (1, 0, 0)  # A is recomputed each run
    assert lock["B"]["status"] == "ok_manual" and b["date_source"] == "human"


def test_KR04_fallback_chain_wef_url_and_retrieved_only_for_bank_charges(
    tmp_path: Path, entry: Callable[..., dict[str, Any]]
) -> None:
    raw, text = tmp_path / "raw", tmp_path / "text"
    raw.mkdir()
    text.mkdir()
    for doc_id in ("W", "U", "R", "X"):
        (raw / f"{doc_id}.html").write_text("<p>Schedule of charges</p>", encoding="utf-8")
    (text / "W.txt").write_text("x " * 3000 + "charges revised w.e.f. 01.04.2025", encoding="utf-8")
    docs = [
        entry(doc_id="W", effective_from=None),
        entry(
            doc_id="U",
            effective_from=None,
            source_url="https://bandhan.bank.in/sites/default/files/2026-08/SoC-21082026.pdf",
        ),
        entry(doc_id="R", effective_from=None, source=13),
        entry(doc_id="X", effective_from=None, source=9),
    ]
    lock: dict[str, dict[str, Any]] = {
        d["doc_id"]: {
            "status": "ok",
            "raw_file": f"{d['doc_id']}.html",
            "retrieved_on": "2026-11-05",
        }
        for d in docs
    }
    apply_dates({"documents": docs}, lock, raw, text)
    got = {d["doc_id"]: (d["effective_from"], d.get("date_source")) for d in docs}
    assert got["W"] == ("2025-04-01", "wef")
    assert got["U"] == ("2026-08-21", "url")  # DDMMYYYY in the file name beats the month folder
    assert got["R"] == ("2026-11-05", "retrieved")
    assert got["X"] == (None, None) and lock["X"]["status"] == "needs_date"  # not bank charges


def test_KR04_url_month_folder_and_pdf_metadata(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    from credassure.datagen.dates import pdf_metadata_date, url_date

    hit = url_date("https://gstcouncil.gov.in/sites/default/files/2024-11/advisory.pdf")
    assert hit is not None and hit[0] == date(2024, 11, 1) and "month folder" in hit[1]
    assert url_date("https://www.cgtmse.in/ViewFile/?id=1767195870980_Circular.pdf") is None
    writer = PdfWriter()
    writer.add_blank_page(100, 100)
    writer.add_metadata({"/CreationDate": "D:20250321103000+05'30'"})
    path = tmp_path / "m.pdf"
    with path.open("wb") as fh:
        writer.write(fh)
    meta = pdf_metadata_date(path)
    assert meta is not None and meta[0] == date(2025, 3, 21)


def test_KR04_implausible_dates_need_review_until_confirmed(
    tmp_path: Path, entry: Callable[..., dict[str, Any]]
) -> None:
    (tmp_path / "A.html").write_text("<p>As on March 31 1985 figures</p>", encoding="utf-8")
    (tmp_path / "B.html").write_text("<p>Circular dated 01.01.2027</p>", encoding="utf-8")
    docs = [entry(doc_id="A", effective_from=None), entry(doc_id="B", effective_from=None)]
    lock: dict[str, dict[str, Any]] = {k: {"status": "ok", "raw_file": f"{k}.html"} for k in "AB"}
    assert apply_dates({"documents": docs}, lock, tmp_path) == (2, 0, 2)
    assert lock["A"]["status"] == lock["B"]["status"] == "needs_review"
    docs[1]["date_confirmed"] = True  # a person confirms the future w.e.f. date
    apply_dates({"documents": docs}, lock, tmp_path)
    assert lock["B"]["status"] == "ok" and lock["A"]["status"] == "needs_review"


def test_KR04_existing_dates_get_a_date_source(
    entry: Callable[..., dict[str, Any]], tmp_path: Path
) -> None:
    docs = [entry(doc_id="R-RBI-02"), entry(doc_id="R-X-001", status="x")]
    lock: dict[str, dict[str, Any]] = {
        "R-RBI-02": {"status": "ok"},
        "R-X-001": {"status": "ok_manual"},
    }
    apply_dates({"documents": docs}, lock, tmp_path)
    assert docs[0]["date_source"] == "curated" and docs[1]["date_source"] == "human"


def test_KR04_review_sample_is_ten_percent_and_deterministic(
    entry: Callable[..., dict[str, Any]],
) -> None:
    docs = [entry(doc_id=f"D{i:02d}", date_source="extracted") for i in range(25)]
    lock = {d["doc_id"]: {"status": "ok", "date_evidence": "dated 01.01.2025"} for d in docs}
    first = review_markdown({"documents": docs}, lock)
    assert first.count("**yes**") == 3  # ceil(25 / 10)
    assert first == review_markdown({"documents": docs}, lock)
