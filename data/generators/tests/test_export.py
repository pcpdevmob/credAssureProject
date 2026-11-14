"""make corpus-export: CORPUS_INDEX.md and .xlsx, one row per manifest entry (KR-01, G2)."""

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from credassure.datagen.export import COLUMNS, export, export_status, rows

SOURCES: dict[str, Any] = {
    "sources": [
        {"id": 4, "name": "CGTMSE", "target": 3, "buffer": 1, "agents": ["LendWise", "Copilot"]},
        {"id": 1, "name": "RBI MD", "target": 2, "agents": ["All"]},
    ]
}


def _fixture(entry: Callable[..., dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    docs = [
        entry(doc_id="R-CG-C-002", source=4, method="script"),
        entry(doc_id="R-CG-C-001", source=4, method="script", source_url="https://www.cgtmse.in/a"),
        entry(doc_id="R-CG-C-003", source=4, method="script", effective_from=None),
        entry(
            doc_id="R-RBI-MD-001", source=1, method="manual", title="PENDING", effective_from=None
        ),
        entry(doc_id="R-RBI-02", source=1, method="manual"),
    ]
    lock = {
        "R-CG-C-001": {"status": "ok"},
        "R-CG-C-002": {"status": "rejected_no_text"},
        "R-CG-C-003": {"status": "needs_review"},
        "R-RBI-MD-001": {"status": "pending_manual", "owner": "[Name 1]"},
        "R-RBI-02": {"status": "ok_manual", "owner": "[Name 1]"},
    }
    return {"documents": docs}, lock


def test_KR01_rows_are_sorted_and_mapped(entry: Callable[..., dict[str, Any]]) -> None:
    manifest, lock = _fixture(entry)
    rs = rows(SOURCES, manifest, lock)
    assert [r["doc_id"] for r in rs] == [
        "R-RBI-02",
        "R-RBI-MD-001",
        "R-CG-C-001",
        "R-CG-C-002",
        "R-CG-C-003",
    ]
    by_id = {r["doc_id"]: r for r in rs}
    assert by_id["R-CG-C-002"]["status"] == "rejected"
    assert by_id["R-CG-C-003"]["status"] == "needs_date"
    assert by_id["R-RBI-MD-001"]["status"] == "pending" and by_id["R-RBI-MD-001"]["manual"] == "Yes"
    assert (
        by_id["R-CG-C-001"]["manual"] == "No"
        and by_id["R-CG-C-001"]["agents"] == "LendWise, Copilot"
    )
    assert list(rs[0]) == COLUMNS
    assert (
        by_id["R-RBI-02"]["downloaded"] == "Yes" and by_id["R-RBI-02"]["agent_name"] == "Supervisor"
    )
    assert by_id["R-RBI-MD-001"]["downloaded"] == "No" and by_id["R-CG-C-002"]["downloaded"] == "No"
    assert by_id["R-CG-C-003"]["downloaded"] == "Yes" and by_id["R-CG-C-001"]["agent_name"] == ""


def test_G2_workbook_layout_links_font_filter_and_formulas(
    tmp_path: Path, entry: Callable[..., dict[str, Any]]
) -> None:
    manifest, lock = _fixture(entry)
    result = export(SOURCES, manifest, lock, tmp_path)
    assert result["available"] == 2 and result["gap"] == 498
    wb = load_workbook(tmp_path / "CORPUS_INDEX.xlsx")
    index, summary = wb["Index"], wb["Summary"]
    assert [c.value for c in index[1]] == COLUMNS
    assert index.auto_filter.ref == "A1:O6" and index.freeze_panes == "A2"
    url_cell = index["D4"]
    assert url_cell.hyperlink is not None and url_cell.hyperlink.target == "https://www.cgtmse.in/a"
    assert all(c.font.name == "Arial" for row in index.iter_rows() for c in row)
    assert all(c.font.name == "Arial" for row in summary.iter_rows() for c in row)
    assert summary["B2"].value.startswith('=COUNTIFS(Index!$G:$G,"ok")')
    assert summary["B4"].value == "=MAX(0,B3-B2)" and summary["B3"].value == 500
    # each per-source formula row points at its own source id in column A
    for r in range(7, 9):
        assert f"A{r}" in summary[f"E{r}"].value and summary[f"A{r}"].value in (4, 1)
    assert wb.calculation.fullCalcOnLoad


def test_G2_markdown_has_summary_and_one_row_per_entry(
    tmp_path: Path, entry: Callable[..., dict[str, Any]]
) -> None:
    manifest, lock = _fixture(entry)
    export(SOURCES, manifest, lock, tmp_path)
    text = (tmp_path / "CORPUS_INDEX.md").read_text(encoding="utf-8")
    assert "**Real available: 2 / 500**" in text
    assert sum(line.startswith("| R-") for line in text.splitlines()) == 5
    assert "[link](https://www.cgtmse.in/a)" in text


def test_G2_export_is_byte_stable(tmp_path: Path, entry: Callable[..., dict[str, Any]]) -> None:
    manifest, lock = _fixture(entry)
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    export(SOURCES, manifest, lock, a)
    time.sleep(1.1)  # openpyxl stamps the save time; a later second must not change the bytes
    export(SOURCES, manifest, lock, b)
    for name in ("CORPUS_INDEX.md", "CORPUS_INDEX.xlsx"):
        assert (a / name).read_bytes() == (b / name).read_bytes()


def test_G2_duplicate_file_is_rejected_not_counted() -> None:
    for status in ("rejected_duplicate", "rejected_language", "rejected_dead_link"):
        assert export_status(status) == "rejected"
