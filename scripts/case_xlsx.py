"""XLSX case authoring kit: an Excel template built from the live schemas, and its converter.

    uv run python scripts/case_xlsx.py template [--out data/templates/case_template.xlsx]
    uv run python scripts/case_xlsx.py convert FILE.xlsx OUT_DIR       # make case-from-xlsx

`template` introspects the upload schemas (core.schemas case files + OfferUpload), so a schema
change shows up on regeneration (a test compares the committed file with a fresh build).
`convert` writes the 5 CSVs, order.json, opening_position.json and offers/<offer_id>.v<n>.json,
after validating each file with the gateway's own upload check (`validate_file`). Errors are
reported by tab, Excel row and column; on any error nothing is written and the exit code is 1.
OUT may not be under data/frozen/ (frozen data is never written). KFS Markdown is free text and
stays a hand-written .md.
"""

import argparse
import csv
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from pydantic import BaseModel

from credassure.core.schemas import OfferUpload
from credassure.datagen.export import FIXED_TIME, _stable_zip

# Sheet layout and conversion are shared with the gateway's Excel import (ADR 0040).
from credassure.gateway.workbook import (
    CHILDREN,
    DATA_ROW,
    FEES_NONE,
    TABS,
    Col,
    Err,
    choices,
    columns,
    is_text,
    lists,
    tab_columns,
    type_label,
)
from credassure.gateway.workbook import convert as _convert

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "data" / "frozen"
TEMPLATE = ROOT / "data" / "templates" / "case_template.xlsx"
EXAMPLE_CASE = "CA-2026-0001"  # becomes CA-2026-0016 through make demo-reset
LAST_ROW = 1000  # text format and dropdowns reach this row
EXAMPLE_FILL = PatternFill("solid", fgColor="FFF4CC")


# ---- template ---------------------------------------------------------------------------------
def _example_rows() -> dict[str, list[dict[str, Any]]]:
    """Frozen EXAMPLE_CASE as tab rows (read only)."""
    src = FROZEN / "v1" / "cases" / EXAMPLE_CASE
    rows: dict[str, list[dict[str, Any]]] = {t: [] for t in (*[t for t, _, _ in TABS], *CHILDREN)}

    def parent(tab: str, rid: str, doc: dict[str, Any], model: type[BaseModel]) -> None:
        row: dict[str, Any] = {"row_id": rid}
        for col in columns(model):
            value: Any = doc
            for part in col.name.split("."):
                value = value.get(part) if isinstance(value, dict) else None
            row[col.name] = value
        for field in lists(model):
            items = doc.get(field)
            if tab == "offers" and items == []:
                row[FEES_NONE] = True
            for item in items or []:
                rows[field].append(
                    {"row_id": rid, **(item if isinstance(item, dict) else {"value": item})}
                )
        rows[tab].append(row)

    for tab, model, kind in TABS:
        if kind == "json":
            parent(tab, "1", json.loads((src / f"{tab}.json").read_text()), model)
        elif kind == "csv":
            with (src / f"{tab}.csv").open(newline="") as fh:
                rows[tab] = list(csv.DictReader(fh))
    offers = sorted((FROZEN / "v1" / "offers" / EXAMPLE_CASE).glob("*.v1.json"))
    for n, path in enumerate(offers, start=1):
        parent("offers", str(n), json.loads(path.read_text()), OfferUpload)
    return rows


def _cell_value(col: Col, raw: Any) -> Any:
    if raw is None or raw == "":
        return None
    if isinstance(raw, bool) or col.ann is bool:
        return str(raw).lower()
    if col.ann in (Decimal, int) and not is_text(col):
        try:
            d = Decimal(str(raw))
        except InvalidOperation:
            return str(raw)  # e.g. "142 lakh": the gateway's money parser reads it
        return int(d) if d == d.to_integral_value() else float(d)
    return str(raw)


def _sheet(wb: Workbook, tab: str, cols: list[Col], rows: list[dict[str, Any]]) -> None:
    ws = wb.create_sheet(tab)
    bold = Font(bold=True)
    for i, col in enumerate(cols, start=1):
        letter = get_column_letter(i)
        ws.cell(1, i, col.name).font = bold
        ws.cell(2, i, type_label(col.ann))
        ws.cell(3, i, "required" if col.required else "optional")
        ws.column_dimensions[letter].width = max(14, len(col.name) + 2)
        if opts := choices(col.ann):
            dv = DataValidation(type="list", formula1='"' + ",".join(opts) + '"', allow_blank=True)
            dv.error, dv.errorTitle = "Pick a value from the list", tab
            dv.add(f"{letter}{DATA_ROW}:{letter}{LAST_ROW}")
            ws.add_data_validation(dv)
        if is_text(col):
            for r in range(DATA_ROW, LAST_ROW + 1):
                ws.cell(r, i).number_format = "@"
    for r, row in enumerate(rows, start=DATA_ROW):
        for i, col in enumerate(cols, start=1):
            cell = ws.cell(r, i, _cell_value(col, row.get(col.name)))
            cell.fill = EXAMPLE_FILL
    ws.freeze_panes = f"A{DATA_ROW}"


README = [
    "CredAssure case template (generated by scripts/case_xlsx.py from the upload schemas).",
    "",
    f"EXAMPLE: the shaded rows are the demo case CA-2026-0016 (frozen {EXAMPLE_CASE}) and its",
    "three v1 offers. Overwrite or delete them before authoring a new case.",
    "",
    "Each tab is one upload file. Row 1 = field, row 2 = type, row 3 = required/optional;",
    f"data starts on row {DATA_ROW}. Use the dropdowns; dates are text YYYY-MM-DD; ids are text.",
    "order and opening_position: exactly one row. costs..inventory: one row per CSV line.",
    "offers: one row per offer version.",
    "",
    "List fields live in their own tabs, linked by row_id to the parent row:",
    "  delivery_weeks -> order, credit_lines and confirmed_mitigations -> opening_position,",
    "  fees -> offers. An offer with no fee rows: fees_none=true means 'no fees';",
    "  blank means the fee schedule is not stated (the audit flags a missing material term).",
    "",
    "Convert:  make case-from-xlsx FILE=my_case.xlsx OUT=var/my_case",
    "Errors are reported as tab, row and column. Upload KFS documents (.md) separately.",
]


def build_template(out: Path) -> None:
    wb = Workbook()
    wb.properties.creator = "scripts/case_xlsx.py"
    wb.properties.created = wb.properties.modified = FIXED_TIME
    ws = wb.worksheets[0]
    ws.title = "README"
    for r, line in enumerate(README, start=1):
        ws.cell(r, 1, line)
    ws.column_dimensions["A"].width = 100
    rows = _example_rows()
    for tab, model, _ in TABS:
        _sheet(wb, tab, tab_columns(tab, model), rows[tab])
    for child, (_, cols) in CHILDREN.items():
        _sheet(wb, child, cols, rows[child])
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    _stable_zip(out)


# ---- convert ----------------------------------------------------------------------------------
def convert(xlsx: Path) -> tuple[dict[str, str], list[Err]]:
    """Workbook -> {relative path: file text}, errors (every sheet required)."""
    return _convert(str(xlsx))


def write(files: dict[str, str], out: Path) -> None:
    for name, text in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def frozen(out: Path) -> bool:
    return out.resolve().is_relative_to(FROZEN.resolve())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="XLSX case authoring kit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("template")
    t.add_argument("--out", type=Path, default=TEMPLATE)
    c = sub.add_parser("convert")
    c.add_argument("file", type=Path)
    c.add_argument("out", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "template":
        if frozen(args.out):
            print("refused: the template may not be written under data/frozen/", file=sys.stderr)
            return 2
        build_template(args.out)
        print(f"wrote {args.out}")
        return 0
    if frozen(args.out):
        print(
            "refused: OUT may not be under data/frozen/ (frozen data is read only)", file=sys.stderr
        )
        return 2
    files, errors = convert(args.file)
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        print(f"{len(errors)} error(s); nothing written", file=sys.stderr)
        return 1
    write(files, args.out)
    print(f"wrote {len(files)} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
