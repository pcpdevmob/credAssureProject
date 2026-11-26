"""Corpus index export (``make corpus-export``, also run by ``make corpus-status``).

Writes ``data/corpus/CORPUS_INDEX.md`` and ``data/corpus/CORPUS_INDEX.xlsx``: one row per manifest entry,
sorted by source then doc_id, plus a summary of real available against the 500 target (BRD G2) by source
and by owner. The workbook summary uses COUNTIFS formulas over the Index sheet, so it recalculates when
rows change (Excel recalculates on open). Both files are byte-stable for the same manifest and lock.

Column meanings:
- **manual**: ``Yes`` for a manual source or placeholder slot; ``No`` for a script entry fetched or
  queued by the script; ``Partial`` for a script entry that needs a person (blocked, failed or imported by hand).
- **status**: ``ok`` / ``ok_manual`` (counted); ``rejected`` (scan without text, or skipped as pre-2015);
  ``needs_date`` (no usable date yet, including dates waiting for review); ``pending`` (everything else).
"""

import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from .corpus import DROPPED, OK, PENDING

COLUMNS = [
    "doc_id",
    "title",
    "source #",
    "url",
    "agents",
    "manual",
    "status",
    "owner",
    "basis",
    "jurisdiction",
    "applies_to",
    "effective_from",
    "date_source",
    "downloaded",
    "agent_name",
]
WIDTHS = [18, 60, 9, 60, 26, 9, 11, 11, 7, 12, 16, 14, 13, 11, 16]
# [Name 1] and [Name 6] are still to be named (PROGRESS.md G1-final checklist)
OWNERS = ["[Name 1]", "Tejas", "Suresh", "Pritish", "Abhishek", "[Name 6]"]
# Owner -> agent they own (BRD §5.2)
OWNER_AGENT = dict(
    zip(
        OWNERS,
        ["Supervisor", "Onboarding", "Working Capital", "LendWise", "Critic", "Copilot"],
        strict=True,
    )
)
TARGET = 500  # BRD §15 G2: at least 500 documents indexed
FIXED_TIME = datetime(2026, 1, 1)  # document properties are fixed so the file is byte-stable
FONT = "Arial"


def export_status(raw: str | None) -> str:
    if raw in OK:
        return str(raw)
    if raw in DROPPED:
        return "rejected"
    if raw in {"needs_date", "needs_review"}:
        return "needs_date"
    return "pending"


def manual_flag(doc: dict[str, Any], status: str | None) -> str:
    if doc["method"] == "manual" or doc["title"] == PENDING:
        return "Yes"
    return "No" if status in {"ok", "pending", None} or status in DROPPED else "Partial"


def rows(
    sources: dict[str, Any], manifest: dict[str, Any], lock: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    agents = {s["id"]: ", ".join(s["agents"]) for s in sources["sources"]}
    out = []
    for d in sorted(manifest["documents"], key=lambda d: (d["source"], d["doc_id"])):
        record = lock.get(d["doc_id"], {})
        raw = record.get("status")
        out.append(
            {
                "doc_id": d["doc_id"],
                "title": d["title"],
                "source #": d["source"],
                "url": d["source_url"],
                "agents": agents.get(d["source"], ""),
                "manual": manual_flag(d, raw),
                "status": export_status(raw),
                "owner": record.get("owner", ""),
                "basis": d["legal_basis"],
                "jurisdiction": d["jurisdiction"],
                "applies_to": d["applies_to"],
                "effective_from": d.get("effective_from") or "",
                "date_source": d.get("date_source") or "",
                # file in hand and accepted (text layer present); pending/rejected are not downloaded
                "downloaded": "No" if export_status(raw) in {"pending", "rejected"} else "Yes",
                "agent_name": OWNER_AGENT.get(record.get("owner", ""), ""),
            }
        )
    return out


def _count(rs: list[dict[str, Any]], **match: Any) -> int:
    return sum(all(r[k] == v for k, v in match.items()) for r in rs)


def summary(sources: dict[str, Any], rs: list[dict[str, Any]]) -> dict[str, Any]:
    def available(**m: Any) -> int:
        return _count(rs, status="ok", **m) + _count(rs, status="ok_manual", **m)

    by_source = [
        {
            "source #": s["id"],
            "name": s["name"],
            "planned": s["target"],
            "buffer": s.get("buffer", 0),
            "available": available(**{"source #": s["id"]}),
            "pending": _count(rs, **{"source #": s["id"], "status": "pending"}),
            "rejected": _count(rs, **{"source #": s["id"], "status": "rejected"}),
            "needs_date": _count(rs, **{"source #": s["id"], "status": "needs_date"}),
        }
        for s in sources["sources"]
    ]
    by_owner = [
        {
            "owner": o,
            "assigned": _count(rs, owner=o),
            "imported": _count(rs, owner=o, status="ok_manual"),
            "pending": _count(rs, owner=o, status="pending"),
        }
        for o in OWNERS
    ]
    total = available()
    return {
        "available": total,
        "gap": max(0, TARGET - total),
        "by_source": by_source,
        "by_owner": by_owner,
    }


def esc(value: Any) -> str:
    return str(value).replace("|", "/")


def markdown(sources: dict[str, Any], rs: list[dict[str, Any]]) -> str:
    s = summary(sources, rs)
    lines = [
        "# Corpus index (ADR 0019)",
        "",
        "Generated by `make corpus-export` (also `make corpus-status`). Do not edit by hand; edit `manifest.yaml`.",
        "One row per manifest entry, sorted by source then doc_id. The spreadsheet version is `CORPUS_INDEX.xlsx`.",
        "",
        f"**Real available: {s['available']} / {TARGET}** (BRD G2). Distance to {TARGET}: **{s['gap']}**. "
        "Synthetic KFS and policies are not counted.",
        "",
        "**manual**: Yes = manual source or placeholder; No = fetched or queued by script; Partial = script entry "
        "that needs a person. **status**: ok / ok_manual (counted), rejected (scan or pre-2015), "
        "needs_date (no usable date yet, including dates under review), pending.",
        "",
        "## By source",
        "",
        "| # | Source | Planned | Buffer | Real available | Pending | Rejected | Needs date |",
        "|---|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['source #']} | {esc(r['name'])} | {r['planned']} | {r['buffer']} | {r['available']} | "
        f"{r['pending']} | {r['rejected']} | {r['needs_date']} |"
        for r in s["by_source"]
    ]
    lines += [
        "",
        "## By owner",
        "",
        "| Owner | Assigned | Imported (ok_manual) | Pending |",
        "|---|---|---|---|",
    ]
    lines += [
        f"| {r['owner']} | {r['assigned']} | {r['imported']} | {r['pending']} |"
        for r in s["by_owner"]
    ]
    lines += ["", "## Index", "", "| " + " | ".join(COLUMNS) + " |", "|" + "---|" * len(COLUMNS)]
    for r in rs:
        cells = [esc(r[c]) for c in COLUMNS]
        cells[3] = f"[link]({r['url']})"
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _stable_zip(path: Path) -> None:
    """Rewrite the .xlsx zip with fixed entry timestamps so identical content gives identical bytes."""
    with zipfile.ZipFile(path) as zin:
        entries = [(i.filename, zin.read(i.filename)) for i in zin.infolist()]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries:
            if name == "docProps/core.xml":  # openpyxl stamps the save time here; pin it
                data = re.sub(
                    rb"(<dcterms:(?:created|modified)[^>]*>)[^<]*",
                    rb"\g<1>2026-01-01T00:00:00Z",
                    data,
                )
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(info, data)


def write_xlsx(sources: dict[str, Any], rs: list[dict[str, Any]], path: Path) -> None:
    wb = Workbook()
    wb.properties.creator = "credassure.datagen.export"
    wb.properties.created = wb.properties.modified = FIXED_TIME
    wb.calculation.fullCalcOnLoad = True  # Summary formulas compute when the workbook opens
    plain, bold = Font(name=FONT, size=10), Font(name=FONT, size=10, bold=True)
    link = Font(name=FONT, size=10, color="0563C1", underline="single")
    head_fill = PatternFill("solid", fgColor="D9D9D9")

    index = wb.worksheets[0]
    index.title = "Index"
    index.append(COLUMNS)
    for r in rs:
        values = [r[c] for c in COLUMNS]
        values[11] = date.fromisoformat(str(r["effective_from"])) if r["effective_from"] else None
        index.append(values)
    for cell in index[1]:
        cell.font, cell.fill = bold, head_fill
    for row in index.iter_rows(min_row=2):
        for cell in row:
            cell.font = plain
        row[3].hyperlink, row[3].font = str(row[3].value), link
        row[11].number_format = "yyyy-mm-dd"
    for i, width in enumerate(WIDTHS, start=1):
        index.column_dimensions[get_column_letter(i)].width = width
    index.freeze_panes = "A2"
    index.auto_filter.ref = f"A1:{get_column_letter(len(COLUMNS))}{len(rs) + 1}"

    sheet = wb.create_sheet("Summary")
    counted = 'COUNTIFS(Index!$G:$G,"ok"{extra})+COUNTIFS(Index!$G:$G,"ok_manual"{extra})'
    sheet.append(["Real corpus vs target (BRD G2)", None])
    sheet.append(["Real available (ok + ok_manual)", "=" + counted.format(extra="")])
    sheet.append(["Target", TARGET])
    sheet.append(["Distance to target", "=MAX(0,B3-B2)"])
    sheet["B3"].font = Font(name=FONT, size=10, color="0000FF")
    sheet["B3"].comment = Comment(
        "BRD §15 gate G2: at least 500 documents indexed. Synthetic KFS and "
        "policies are not counted (ADR 0019).",
        "credassure",
    )
    sheet.append([])
    start = sheet.max_row + 1
    sheet.append(
        [
            "Source #",
            "Name",
            "Planned",
            "Buffer",
            "Real available",
            "Pending",
            "Rejected",
            "Needs date",
            "Gap to planned",
        ]
    )
    for s in sources["sources"]:
        r = sheet.max_row + 1
        sheet.append(
            [
                s["id"],
                s["name"],
                s["target"],
                s.get("buffer", 0),
                "=" + counted.format(extra=f",Index!$C:$C,A{r}"),
                f'=COUNTIFS(Index!$C:$C,A{r},Index!$G:$G,"pending")',
                f'=COUNTIFS(Index!$C:$C,A{r},Index!$G:$G,"rejected")',
                f'=COUNTIFS(Index!$C:$C,A{r},Index!$G:$G,"needs_date")',
                f"=MAX(0,C{r}-E{r})",
            ]
        )
    end = sheet.max_row
    sheet.append(["Total", None] + [f"=SUM({col}{start + 1}:{col}{end})" for col in "CDEFGHI"])
    sheet.cell(row=start + 1, column=3).comment = Comment(
        "Planned and Buffer come from data/corpus/sources.yaml (owner targets, ADR 0019).",
        "credassure",
    )
    sheet.append([])
    owner_head = sheet.max_row + 1
    sheet.append(["Owner", "Assigned", "Imported (ok_manual)", "Pending"])
    for o in OWNERS:
        r = sheet.max_row + 1
        sheet.append(
            [
                o,
                f"=COUNTIF(Index!$H:$H,A{r})",
                f'=COUNTIFS(Index!$H:$H,A{r},Index!$G:$G,"ok_manual")',
                f'=COUNTIFS(Index!$H:$H,A{r},Index!$G:$G,"pending")',
            ]
        )
    for row in sheet.iter_rows():
        for cell in row:
            cell.font = plain
    for coord in ("A1", f"A{start}", f"A{end + 1}", f"A{owner_head}"):
        sheet[coord].font = bold
    for header_row in (start, owner_head):
        for cell in sheet[header_row]:
            if cell.value is not None:
                cell.font, cell.fill = bold, head_fill
    sheet["B3"].font = Font(name=FONT, size=10, color="0000FF")
    for col, width in zip("ABCDEFGHI", [32, 60, 10, 9, 15, 10, 10, 12, 15], strict=True):
        sheet.column_dimensions[col].width = width
    wb.save(path)
    _stable_zip(path)


def export(
    sources: dict[str, Any], manifest: dict[str, Any], lock: dict[str, dict[str, Any]], folder: Path
) -> dict[str, Any]:
    rs = rows(sources, manifest, lock)
    (folder / "CORPUS_INDEX.md").write_text(markdown(sources, rs), encoding="utf-8", newline="\n")
    write_xlsx(sources, rs, folder / "CORPUS_INDEX.xlsx")
    return summary(sources, rs)
