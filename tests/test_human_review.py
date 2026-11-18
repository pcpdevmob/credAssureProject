"""docs/plan/human-review.xlsx stays in step with human-review.md (the source of truth)."""

import importlib.util
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("hrx", ROOT / "scripts" / "human_review_xlsx.py")
assert _spec and _spec.loader
hrx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hrx)


def test_sheet_matches_the_markdown() -> None:
    header, rows = hrx.parse(hrx.MD.read_text(encoding="utf-8"))
    ws = load_workbook(hrx.XLSX)["Review items"]
    got = [[str(c.value or "") for c in r][: len(header)] for r in ws.iter_rows(min_row=1)]
    assert got == [header, *rows], "run: uv run python scripts/human_review_xlsx.py"


def test_every_row_has_an_id_and_a_known_status() -> None:
    header, rows = hrx.parse(hrx.MD.read_text(encoding="utf-8"))
    ids = [r[0] for r in rows]
    assert len(ids) == len(set(ids)) and all(i.startswith("H") for i in ids)
    status = header.index("Status")
    assert all(r[status] in hrx.STATUSES for r in rows)
