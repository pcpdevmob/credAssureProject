"""Generate docs/plan/human-review.xlsx from docs/plan/human-review.md (the source of truth).

The sheet is for team discussion: Status is a drop-down, and Notes / Signed off / Date are free
columns. Record the outcome back in the Markdown file and regenerate; a test fails when the
sheet no longer matches the Markdown.

    uv run python scripts/human_review_xlsx.py
"""

import re
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "docs" / "plan" / "human-review.md"
XLSX = ROOT / "docs" / "plan" / "human-review.xlsx"
STATUSES = ("Open", "In review", "Accepted", "Changed", "Rejected")
EXTRA = ("Discussion notes", "Date")
WIDTHS = {"#": 6, "Phase": 9, "Item": 34, "Artefact": 34, "Accepted as": 28}
WIDTHS |= {"Why it still needs a review": 60, "Decision needed": 40, "Suggested reviewer": 22}
WIDTHS |= {"Blocks": 20, "Status": 12, "Signed off": 16, "Discussion notes": 40, "Date": 12}


def _cells(line: str) -> list[str]:
    return [c.strip().replace("`", "") for c in line.strip().strip("|").split("|")]


def parse(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in text.splitlines() if ln.startswith("|")]
    header = _cells(lines[0])
    rows = [_cells(ln) for ln in lines[2:] if re.match(r"\|\s*H\d+", ln)]
    return header, rows


def build(text: str) -> Workbook:
    header, rows = parse(text)
    wb = Workbook()
    ws = wb.active
    assert ws is not None  # noqa: S101 - a new workbook always has a sheet
    ws.title = "Review items"
    cols = [*header, *EXTRA]
    ws.append(cols)
    for row in rows:
        ws.append([*row, *([""] * len(EXTRA))])
    font, bold = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True, color="FFFFFF")
    thin = Side(style="thin", color="BFBFBF")
    for line in ws.iter_rows():
        for c in line:
            c.font = font
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = Border(top=thin, bottom=thin, left=thin, right=thin)
    fill = PatternFill("solid", fgColor="1F4E79")
    for c in ws[1]:
        c.font, c.fill = bold, fill
    edit = PatternFill("solid", fgColor="FFF2CC")  # cells the team fills in
    for name in ("Status", "Signed off", *EXTRA):
        col = cols.index(name) + 1
        for n in range(2, len(rows) + 2):
            ws.cell(n, col).fill = edit
    for i, name in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(i)].width = WIDTHS.get(name, 18)
    status_col = get_column_letter(cols.index("Status") + 1)
    dv = DataValidation(type="list", formula1=f'"{",".join(STATUSES)}"', allow_blank=False)
    ws.add_data_validation(dv)
    dv.add(f"{status_col}2:{status_col}{len(rows) + 1}")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions

    legend = wb.create_sheet("How to use")
    for note in (
        "Human review list (plan v3.4) - generated from docs/plan/human-review.md",
        "",
        "Yellow cells are for the team: Status (drop-down), Signed off, Discussion notes, Date.",
        "Status: Open, In review, Accepted, Changed, Rejected.",
        "Reviewer rule (G1, ADR 0031): nobody reviews items, labels or tests for a module"
        " they own.",
        "After the meeting, copy outcomes into docs/plan/human-review.md (the source of truth),",
        "then regenerate this file: uv run python scripts/human_review_xlsx.py",
        "Example: H7 | Status = Accepted | Signed off = Tejas | Notes = S12 reworded"
        " | Date = 2026-11-19",
    ):
        legend.append([note])
        legend.cell(legend.max_row, 1).font = Font(name="Arial", size=10, bold=legend.max_row == 1)
    legend.column_dimensions["A"].width = 100
    return wb


def main() -> int:
    build(MD.read_text(encoding="utf-8")).save(XLSX)
    print(f"wrote {XLSX.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
