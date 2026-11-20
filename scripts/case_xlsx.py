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
import io
import json
import sys
import types
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import BaseModel

from credassure.core.schemas import (
    CostRow,
    InventoryRow,
    OfferUpload,
    OpeningPosition,
    OrderFile,
    PayableRow,
    ReceiptRow,
    ReceivableRow,
)
from credassure.datagen.export import FIXED_TIME, _stable_zip
from credassure.gateway.problems import ProblemError
from credassure.gateway.routers.cases import validate_file

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "data" / "frozen"
TEMPLATE = ROOT / "data" / "templates" / "case_template.xlsx"
EXAMPLE_CASE = "CA-2026-0001"  # becomes CA-2026-0016 through make demo-reset
DATA_ROW = 4  # rows 1-3: field name, type, required/optional
LAST_ROW = 1000  # text format and dropdowns reach this row
EXAMPLE_FILL = PatternFill("solid", fgColor="FFF4CC")

# (tab = upload kind, schema, file kind); parents of list fields get a row_id column
TABS: tuple[tuple[str, type[BaseModel], str], ...] = (
    ("order", OrderFile, "json"),
    ("opening_position", OpeningPosition, "json"),
    ("costs", CostRow, "csv"),
    ("receipts", ReceiptRow, "csv"),
    ("receivables", ReceivableRow, "csv"),
    ("payables", PayableRow, "csv"),
    ("inventory", InventoryRow, "csv"),
    ("offers", OfferUpload, "offer"),
)
FEES_NONE = (
    "fees_none"  # offers: true = the offer states no fees ([]); blank + no fee rows = absent
)


@dataclass(frozen=True)
class Col:
    name: str
    ann: Any
    required: bool


def _inner(ann: Any) -> tuple[Any, bool]:
    """(type without None, optional?)"""
    if get_origin(ann) in (Union, types.UnionType):
        args = [a for a in get_args(ann) if a is not type(None)]
        return args[0], len(args) < len(get_args(ann))
    return ann, False


def _is_model(ann: Any) -> bool:
    return isinstance(ann, type) and issubclass(ann, BaseModel)


def columns(model: type[BaseModel], prefix: str = "", required: bool = True) -> list[Col]:
    """Flat columns of a model; nested models become dotted columns, list fields are skipped."""
    out: list[Col] = []
    for name, f in model.model_fields.items():
        ann, _ = _inner(f.annotation)
        if name == "schema_version" or get_origin(ann) is list:
            continue
        if _is_model(ann):
            out += columns(ann, f"{prefix}{name}.", required and f.is_required())
        else:
            out.append(Col(prefix + name, ann, required and f.is_required()))
    return out


def lists(model: type[BaseModel]) -> dict[str, Any]:
    """List fields of a model -> item type."""
    return {
        n: get_args(_inner(f.annotation)[0])[0]
        for n, f in model.model_fields.items()
        if get_origin(_inner(f.annotation)[0]) is list
    }


def item_columns(item: Any) -> list[Col]:
    return columns(item) if _is_model(item) else [Col("value", item, True)]


def tab_columns(tab: str, model: type[BaseModel]) -> list[Col]:
    cols = columns(model)
    if tab in PARENTS:
        cols = [Col("row_id", str, True), *cols]
    if tab == "offers":
        cols.append(Col(FEES_NONE, bool, False))
    return cols


PARENTS = {tab for tab, model, _ in TABS if lists(model)}
CHILDREN: dict[str, tuple[str, list[Col]]] = {  # child tab -> (parent tab, columns)
    field: (tab, [Col("row_id", str, True), *item_columns(item)])
    for tab, model, _ in TABS
    for field, item in lists(model).items()
}
SCALAR_CHILDREN = {
    c for c, (_, cols) in CHILDREN.items() if [x.name for x in cols] == ["row_id", "value"]
}


def type_label(ann: Any) -> str:
    if get_origin(ann) is Literal:
        return "one of: " + ", ".join(str(a) for a in get_args(ann))
    return {
        bool: "true/false",
        date: "date YYYY-MM-DD",
        Decimal: "decimal (plain digits or ₹ Indian format)",
        int: "whole number",
    }.get(ann, "text")


def choices(ann: Any) -> list[str] | None:
    if get_origin(ann) is Literal:
        return [str(a) for a in get_args(ann)]
    return ["true", "false"] if ann is bool else None


def is_text(col: Col) -> bool:
    """Excel must not reformat these: dates, booleans and ids."""
    return col.ann in (date, bool) or col.name.endswith(("_id", "_ref")) or col.name == "row_id"


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
@dataclass
class Err:
    tab: str
    row: int | None
    column: str | None
    reason: str

    def __str__(self) -> str:
        where = f"row {self.row}" if self.row else "tab"
        col = f", column {self.column}" if self.column else ""
        return f"{self.tab}: {where}{col}: {self.reason}"


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    return str(value).strip()


def _read(ws: Worksheet) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    header = [_text(c.value) for c in ws[1]]
    rows = []
    for r, cells in enumerate(ws.iter_rows(min_row=DATA_ROW, values_only=True), start=DATA_ROW):
        values = {h: _text(v) for h, v in zip(header, cells, strict=False) if h}
        if any(values.values()):
            rows.append((r, values))
    return header, rows


def _nest(values: dict[str, str]) -> dict[str, Any]:
    """Dotted columns -> nested dict; blank cells are absent."""
    out: dict[str, Any] = {}
    for key, value in values.items():
        if value == "":
            continue
        *path, leaf = key.split(".")
        node = out
        for part in path:
            node = node.setdefault(part, {})
        node[leaf] = value
    return out


def convert(xlsx: Path) -> tuple[dict[str, str], list[Err]]:
    """Workbook -> {relative path: file text}, errors. Validation is the gateway's own."""
    wb = load_workbook(xlsx)  # formulas stay "=..." text: the gateway refuses them
    errors: list[Err] = []
    sheets: dict[str, tuple[list[str], list[tuple[int, dict[str, str]]]]] = {}
    for tab in (*[t for t, _, _ in TABS], *CHILDREN):
        if tab not in wb.sheetnames:
            errors.append(Err(tab, None, None, "tab is missing"))
        else:
            sheets[tab] = _read(wb[tab])
    if errors:
        return {}, errors

    # child rows grouped by (parent tab, row_id); orphans are errors
    parent_ids = {t: {v.get("row_id", "") for _, v in sheets[t][1]} for t in PARENTS}
    children: dict[tuple[str, str], list[tuple[str, int, dict[str, str]]]] = {}
    for child, (parent, _) in CHILDREN.items():
        for r, values in sheets[child][1]:
            rid = values.pop("row_id", "")
            if rid not in parent_ids[parent] or not rid:
                errors.append(Err(child, r, "row_id", f"no {parent} row has row_id {rid!r}"))
            else:
                children.setdefault((parent, rid), []).append((child, r, values))

    files: dict[str, str] = {}
    for tab, _model, kind in TABS:
        header, rows = sheets[tab]
        if kind == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf, lineterminator="\n")
            cols = [h for h in header if h]
            writer.writerow(cols)
            for _, values in rows:
                writer.writerow([values.get(c, "") for c in cols])
            excel_rows = [r for r, _ in rows]
            errors += _check(tab, tab, buf.getvalue(), f"{tab}.csv", files, csv_rows=excel_rows)
            continue
        if kind == "json" and len(rows) != 1:
            errors.append(Err(tab, None, None, f"needs exactly one row (has {len(rows)})"))
            continue
        seen: set[str] = set()
        for r, values in rows:
            rid = values.pop("row_id", "")
            fees_none = values.pop(FEES_NONE, "").lower()
            doc = _nest(values)
            where: dict[tuple[str, int], tuple[str, int]] = {}
            for child, cr, cvalues in children.get((tab, rid), []):
                items = doc.setdefault(child, [])
                where[(child, len(items))] = (child, cr)
                items.append(cvalues["value"] if child in SCALAR_CHILDREN else _nest(cvalues))
            if tab == "offers":
                if fees_none == "true" and doc.get("fees"):
                    errors.append(Err(tab, r, FEES_NONE, "fees_none is true but fee rows exist"))
                elif fees_none == "true":
                    doc["fees"] = []
                name = f"offers/{doc.get('offer_id', '')}.v{doc.get('version', '')}.json"
                if name in seen:
                    errors.append(Err(tab, r, "offer_id", "offer_id and version repeat a row"))
                seen.add(name)
                kind_ = "offer"
            else:
                name, kind_ = f"{tab}.json", tab
            text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
            errors += _check(kind_, tab, text, name, files, json_row=r, where=where)
    return files, errors


def _check(
    kind: str,
    tab: str,
    text: str,
    name: str,
    files: dict[str, str],
    *,
    csv_rows: list[int] | None = None,
    json_row: int | None = None,
    where: dict[tuple[str, int], tuple[str, int]] | None = None,
) -> list[Err]:
    """The gateway's upload check; its {field,row,reason} errors mapped back to tab/row/column."""
    try:
        payload, _ = validate_file(kind, text)
    except ProblemError as exc:
        out = []
        for e in exc.errors or [{"field": None, "row": None, "reason": exc.detail}]:
            field, row, reason = e.get("field"), e.get("row"), str(e.get("reason"))
            if csv_rows is not None:
                if "not allowed in case files" in reason and row:  # PII: row is a text line
                    row -= 1
                xrow = csv_rows[row - 1] if row and 0 < row <= len(csv_rows) else None
                out.append(Err(tab, xrow, field, reason))
                continue
            parts = (field or "").split(".")
            if (
                where
                and len(parts) > 1
                and parts[1].isdigit()
                and (parts[0], int(parts[1])) in where
            ):
                ctab, crow = where[(parts[0], int(parts[1]))]
                out.append(Err(ctab, crow, ".".join(parts[2:]) or "value", reason))
            else:
                out.append(Err(tab, json_row, field, reason))
        return out
    # JSON: the validated payload (typed, canonical); re-uploading it validates to the same payload
    files[name] = text if csv_rows is not None else json.dumps(payload, indent=2) + "\n"
    return []


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
