"""Excel case workbook -> the case's JSON/CSV files (UI-02; ADR 0040).

The workbook is the team's case template (`data/templates/case_template.xlsx`, built by
`scripts/case_xlsx.py` from the upload schemas): one sheet per case file plus `offers`, list
fields in child sheets linked by `row_id`. `convert` turns it into exactly the files a person could
upload one by one (`order.json`, `costs.csv`, ..., `offers/<id>.v<n>.json`) and checks each with
the upload's own `validate_file`; errors name sheet, Excel row and column. Nothing here calculates
or decides anything: the stored files are the same as an upload and every stage reads them as
before.

Untrusted input: the size is capped before parsing, the zip is inspected (entry count, total
uncompressed size) so a zip bomb is refused, openpyxl parses XML through defusedxml, formulas are
read as their "=..." text (refused by the upload check, never evaluated), and rows per sheet are
capped.
"""

import csv
import io
import json
import types
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, BinaryIO, Literal, Union, get_args, get_origin

from openpyxl import load_workbook
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
from credassure.gateway.problems import ProblemError
from credassure.gateway.routers.cases import validate_file

DATA_ROW = 4  # rows 1-3: field name, type, required/optional
MAX_ROWS = 5000  # per sheet; far above any case file
MAX_ENTRIES = 500  # zip entries in one workbook
MAX_UNZIPPED = 40 * 1024 * 1024  # 40 MB of XML at most (zip bomb guard)

# (sheet = upload kind, schema, file kind); parents of list fields get a row_id column
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


PARENTS = {tab for tab, model, _ in TABS if lists(model)}


def tab_columns(tab: str, model: type[BaseModel]) -> list[Col]:
    cols = columns(model)
    if tab in PARENTS:
        cols = [Col("row_id", str, True), *cols]
    if tab == "offers":
        cols.append(Col(FEES_NONE, bool, False))
    return cols


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


Rows = list[tuple[int, dict[str, str]]]


def _read(ws: Any, tab: str, errors: list[Err]) -> tuple[list[str], Rows]:
    it = ws.iter_rows(values_only=True)
    first = next(it, None) or ()
    header = [_text(v) for v in first]
    rows: Rows = []
    for r, cells in enumerate(ws.iter_rows(min_row=DATA_ROW, values_only=True), start=DATA_ROW):
        values = {h: _text(v) for h, v in zip(header, cells, strict=False) if h}
        if any(values.values()):
            if len(rows) >= MAX_ROWS:
                errors.append(Err(tab, r, None, f"more than {MAX_ROWS} rows"))
                break
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


def guard_zip(data: bytes) -> None:
    """Refuse anything that is not a small, sane .xlsx zip before openpyxl reads it."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = z.infolist()
    except zipfile.BadZipFile as exc:
        raise ProblemError(
            422,
            "not an Excel workbook",
            errors=[{"field": None, "row": None, "reason": "the file is not a .xlsx workbook"}],
        ) from exc
    if len(infos) > MAX_ENTRIES or sum(i.file_size for i in infos) > MAX_UNZIPPED:
        raise ProblemError(
            422,
            "workbook too large",
            errors=[{"field": None, "row": None, "reason": "the workbook is too large to read"}],
        )
    if "[Content_Types].xml" not in {i.filename for i in infos}:
        raise ProblemError(
            422,
            "not an Excel workbook",
            errors=[{"field": None, "row": None, "reason": "the file is not a .xlsx workbook"}],
        )


def convert(source: str | BinaryIO, *, partial: bool = False) -> tuple[dict[str, str], list[Err]]:
    """Workbook -> {relative path: file text}, errors. Validation is the upload's own.

    partial=False (the authoring script): every sheet must exist and hold data.
    partial=True (the web upload): a missing or empty sheet is skipped, so a person can send only
    the sections they have; a workbook with no recognised sheet at all is an error.
    """
    wb = load_workbook(source, read_only=True, data_only=False, keep_links=False)
    errors: list[Err] = []
    sheets: dict[str, tuple[list[str], Rows]] = {}
    try:
        for tab in (*[t for t, _, _ in TABS], *CHILDREN):
            if tab in wb.sheetnames:
                sheets[tab] = _read(wb[tab], tab, errors)
            elif partial:
                sheets[tab] = ([], [])
            else:
                errors.append(Err(tab, None, None, "tab is missing"))
    finally:
        wb.close()
    if errors:
        return {}, errors
    if partial and not any(rows for _, rows in sheets.values()):
        known = ", ".join(t for t, _, _ in TABS)
        return {}, [Err("workbook", None, None, f"no case sheets with data (expected: {known})")]

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
        if partial and not rows:
            continue
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
    """The upload's own check; its {field,row,reason} errors mapped back to sheet/row/column."""
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


def kind_of(name: str) -> str:
    """'costs.csv' -> 'costs'; 'offers/OF-01-A.v1.json' -> 'offer'."""
    return "offer" if name.startswith("offers/") else name.rsplit(".", 1)[0]
