"""Effective dates for available corpus documents (KR-04 date filter, ADR 0019).

``candidate_date`` reads the first two pages (PDF) or the first 6,000 characters (HTML) and prefers a
labelled date ("dated", "Date:", "w.e.f.", "with effect from", "issued on") over the first plain date.
It handles Indian formats: 12.10.2026, 12/10/2026, 12-10-2026, 2026-10-12, 12 October 2026,
12th October, 2026, October 12, 2026. ``apply_dates`` sets ``effective_from`` with
``date_source: extracted``. A document with no findable date becomes ``needs_date``, which does
not count as available, until a person fills the date (``date_source: human``). A seeded 10% sample
of extracted dates is flagged for a human check in ``DATE_REVIEW.md``.
"""

import math
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from pypdf import PdfReader

from .common import AS_OF_DATE, rng
from .corpus import OK, extract_text

EARLIEST, LATEST = (
    date(1950, 1, 1),
    date(2035, 12, 31),
)  # extraction window: implausible dates surface
PLAUSIBLE_FROM = date(
    1990, 1, 1
)  # plausibility rule: before this or after AS_OF_DATE -> needs_review
BANK_CHARGES_SOURCE = 13  # the only source where "retrieved" (current as of) is an allowed date
PENDING_DATE = {"needs_date", "needs_review"}
MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
        start=1,
    )
}
_MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_YEAR = r"((?:19|20)\d{2})"
PATTERNS = [
    ("iso", re.compile(rf"\b{_YEAR}-(\d{{2}})-(\d{{2}})\b")),
    ("dmy", re.compile(rf"\b(\d{{1,2}})[./-](\d{{1,2}})[./-]{_YEAR}\b")),
    ("d_mon_y", re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+{_MON},?\s+{_YEAR}\b", re.I)),
    ("mon_d_y", re.compile(rf"\b{_MON}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+{_YEAR}\b", re.I)),
]
# Hindi month names by prefix, so text-layer garbling ("फिविी" for फरवरी) still maps to the month.
HINDI_MONTHS = [
    ("जन", 1),
    ("फ", 2),
    ("मार्", 3),
    ("मा", 3),
    ("अप्र", 4),
    ("मई", 5),
    ("जून", 6),
    ("जू", 6),
    ("जुल", 7),
    ("अग", 8),
    ("सित", 9),
    ("अक्", 10),
    ("नव", 11),
    ("दिस", 12),
]
_DEV = r"([\u0900-\u097F]+)"
PATTERNS += [
    ("d_hmon_y", re.compile(rf"\b(\d{{1,2}})\s+{_DEV},?\s+{_YEAR}\b")),
    ("hmon_d_y", re.compile(rf"{_DEV}\s+(\d{{1,2}}),?\s+{_YEAR}\b")),
]
HEADER_CHARS = 400
WEEKDAY = re.compile(r"(?:mon|tues|wednes|thurs|fri|satur|sun)day,?\s*$", re.I)
LABEL = re.compile(
    r"(?:dated|date\s*[:\-]|w\.\s?e\.\s?f\.?|with\s+effect\s+from|issued\s+on)\s*[:\-]?\s*(?:the\s+)?$",
    re.I,
)


def _hindi_month(word: str) -> int:
    for prefix, month in sorted(HINDI_MONTHS, key=lambda x: -len(x[0])):
        if word.startswith(prefix):
            return month
    raise ValueError(word)


def _to_date(kind: str, groups: tuple[str, ...]) -> date | None:
    try:
        if kind == "d_hmon_y":
            return date(int(groups[2]), _hindi_month(groups[1]), int(groups[0]))
        if kind == "hmon_d_y":
            return date(int(groups[2]), _hindi_month(groups[0]), int(groups[1]))
        if kind == "iso":
            return date(int(groups[0]), int(groups[1]), int(groups[2]))
        if kind == "dmy":
            return date(int(groups[2]), int(groups[1]), int(groups[0]))
        if kind == "d_mon_y":
            return date(int(groups[2]), MONTHS[groups[1].lower()[:3]], int(groups[0]))
        return date(int(groups[2]), MONTHS[groups[0].lower()[:3]], int(groups[1]))
    except ValueError:
        return None


def candidate_date(text: str, ignore: date | None = None) -> tuple[date, str] | None:
    """(date, snippet): a date in the letterhead (first 400 characters) first, then a labelled one,
    then the first plain one. Page clocks (weekday-prefixed dates, the retrieval date) are ignored."""
    found: list[tuple[int, bool, date, str]] = []
    for kind, pattern in PATTERNS:
        for m in pattern.finditer(text):
            day = _to_date(kind, m.groups())
            if day is None or not EARLIEST <= day <= LATEST or day == ignore:
                continue
            if WEEKDAY.search(text[max(0, m.start() - 12) : m.start()]):
                continue  # "Thursday, November 05, 2026": a website clock, not the document date
            labelled = bool(LABEL.search(text[max(0, m.start() - 40) : m.start()]))
            snippet = " ".join(text[max(0, m.start() - 30) : m.end() + 10].split())[:80]
            found.append((m.start(), labelled, day, snippet))
    if not found:
        return None
    header = sorted(f for f in found if f[0] < HEADER_CHARS)
    with_label = sorted(f for f in found if f[1])
    _, _, day, snippet = (header or with_label or sorted(found))[0]
    return day, snippet


def first_pages(raw: Path, fmt: str) -> str:
    body = raw.read_bytes()
    if fmt == "pdf":
        try:
            pages = PdfReader(BytesIO(body)).pages[:2]
            return "\n".join((p.extract_text() or "") for p in pages)
        except Exception:
            return ""
    return extract_text(body, "html")[:6000]


WEF = re.compile(
    r"(?:w\.\s?e\.\s?f\.?|with\s+effect\s+from|effective\s+(?:from|date))\s*[:\-]?\s*(?:the\s+)?$",
    re.I,
)
URL_PATTERNS = [
    ("ymd", re.compile(r"(?<!\d)(20\d{2}|19\d{2})-(\d{2})-(\d{2})(?!\d)")),
    ("dmy", re.compile(r"(?<!\d)(\d{2})[-.](\d{2})[-.]((?:19|20)\d{2})(?!\d)")),
    ("ddmmyyyy", re.compile(r"(?<!\d)(\d{2})(\d{2})((?:19|20)\d{2})(?!\d)")),
    ("yyyymmdd", re.compile(r"(?<!\d)((?:19|20)\d{2})(\d{2})(\d{2})(?!\d)")),
    ("folder", re.compile(r"/((?:19|20)\d{2})[/-](\d{2})/")),
]


def wef_date(text: str) -> tuple[date, str] | None:
    """(a) "w.e.f." / "with effect from" / "effective from" anywhere in the full text."""
    hits = []
    for kind, pattern in PATTERNS:
        for m in pattern.finditer(text):
            day = _to_date(kind, m.groups())
            if (
                day
                and EARLIEST <= day <= LATEST
                and WEF.search(text[max(0, m.start() - 40) : m.start()])
            ):
                hits.append(
                    (m.start(), day, " ".join(text[max(0, m.start() - 30) : m.end()].split())[:80])
                )
    return (min(hits)[1], min(hits)[2]) if hits else None


def url_date(url: str) -> tuple[date, str] | None:
    """(b) a date in the URL or file name; an upload folder /YYYY/MM/ gives day 1 of that month."""
    text = unquote(url)
    for kind, pattern in URL_PATTERNS:
        for m in pattern.finditer(text):
            g = m.groups()
            try:
                if kind == "ymd" or kind == "yyyymmdd":
                    day = date(int(g[0]), int(g[1]), int(g[2]))
                elif kind in {"dmy", "ddmmyyyy"}:
                    day = date(int(g[2]), int(g[1]), int(g[0]))
                else:
                    day = date(int(g[0]), int(g[1]), 1)
            except ValueError:
                continue
            if EARLIEST <= day <= LATEST:
                return (
                    day,
                    f"url {'month folder' if kind == 'folder' else kind}: {m.group(0).strip('/')}",
                )
    return None


def pdf_metadata_date(raw: Path) -> tuple[date, str] | None:
    """(c) PDF CreationDate, else ModDate."""
    try:
        meta = PdfReader(raw).metadata
    except Exception:
        return None
    for label, value in (
        ("CreationDate", getattr(meta, "creation_date", None)),
        ("ModDate", getattr(meta, "modification_date", None)),
    ):
        if value is not None:
            day = value.date()
            if EARLIEST <= day <= LATEST:
                return day, f"pdf metadata {label}"
    return None


def date_chain(
    d: dict[str, Any], record: dict[str, Any], raw_dir: Path, text_dir: Path
) -> tuple[date, str, str] | None:
    """(date, date_source, evidence): page text, then (a) wef, (b) url, (c) pdf metadata, (d) retrieved."""
    raw = raw_dir / record.get("raw_file", "")
    retrieved = record.get("retrieved_on")
    ignore = date.fromisoformat(str(retrieved)) if retrieved else None
    if raw.is_file():
        if hit := candidate_date(first_pages(raw, d["format"]), ignore):
            return hit[0], "extracted", hit[1]
        full = text_dir / f"{d['doc_id']}.txt"
        if full.is_file() and (hit := wef_date(full.read_text(encoding="utf-8"))):
            return hit[0], "wef", hit[1]
    if hit := url_date(d["source_url"]):
        return hit[0], "url", hit[1]
    if raw.is_file() and d["format"] == "pdf" and (hit := pdf_metadata_date(raw)):
        return hit[0], "pdf_metadata", hit[1]
    if d["source"] == BANK_CHARGES_SOURCE and retrieved:
        return date.fromisoformat(str(retrieved)), "retrieved", "current as of the retrieval date"
    return None


def _origin(d: dict[str, Any], status: str | None) -> str:
    """date_source for a date that predates this tool: a person's, or a hand-curated manifest entry."""
    if status == "ok_manual":
        return "human"
    return "extracted" if re.search(r"-\d{3}$", d["doc_id"]) else "curated"


def apply_dates(
    manifest: dict[str, Any],
    lock: dict[str, dict[str, Any]],
    raw_dir: Path,
    text_dir: Path | None = None,
) -> tuple[int, int, int]:
    """Date every document with text. Returns (dated by the chain, needs a date, needs review).

    Dates from ``human`` or ``curated`` are kept; every other date is recomputed each run. A date
    before 1990 or after AS_OF_DATE needs review unless ``date_confirmed`` or ``date_source: human``.
    """
    text_dir = text_dir or raw_dir.parent / "text"
    chained = undated = review = 0
    for d in manifest["documents"]:
        record = lock.get(d["doc_id"], {})
        status = record.get("status")
        if status not in OK | PENDING_DATE or record.get("review_reason"):
            continue  # junk-page review (make corpus-junk) is not a date question
        base = record.get("status_before_date", status) if status in PENDING_DATE else status
        if d.get("effective_from") and not d.get("date_source"):
            d["date_source"] = _origin(d, base)
        if d.get("date_source") not in {"human", "curated"}:
            hit = date_chain(d, record, raw_dir, text_dir)
            if hit is None:
                d["effective_from"] = None
                d.pop("date_source", None)
                record.pop("date_evidence", None)
            else:
                d["effective_from"], d["date_source"], record["date_evidence"] = (
                    hit[0].isoformat(),
                    hit[1],
                    hit[2],
                )
                chained += 1
        day = d.get("effective_from")
        confirmed = d.get("date_confirmed") or d.get("date_source") == "human"
        if not day:
            new = "needs_date"
        elif not confirmed and not PLAUSIBLE_FROM <= date.fromisoformat(str(day)) <= AS_OF_DATE:
            new = "needs_review"
        else:
            new = base
        if new in PENDING_DATE:
            record["status_before_date"] = base
            undated += new == "needs_date"
            review += new == "needs_review"
        else:
            record.pop("status_before_date", None)
        record["status"] = new
    return chained, undated, review


REVIEWED = ("extracted", "wef", "url", "pdf_metadata", "retrieved")


def review_markdown(manifest: dict[str, Any], lock: dict[str, dict[str, Any]]) -> str:
    docs = sorted(manifest["documents"], key=lambda d: d["doc_id"])
    status = {d["doc_id"]: lock.get(d["doc_id"], {}).get("status") for d in docs}
    dated = [d for d in docs if d.get("date_source") in REVIEWED and status[d["doc_id"]] in OK]
    sample: set[str] = set()
    for kind in REVIEWED:  # a seeded 10% per date_source, so every fallback kind is checked
        ids = [d["doc_id"] for d in dated if d["date_source"] == kind]
        if ids:
            sample |= set(rng(f"date-review:{kind}").sample(ids, math.ceil(len(ids) / 10)))
    review = [d for d in docs if status[d["doc_id"]] == "needs_review"]
    undated = [d for d in docs if status[d["doc_id"]] == "needs_date"]

    def row(d: dict[str, Any], check: str = "") -> str:
        evidence = lock.get(d["doc_id"], {}).get("date_evidence", "").replace("|", "/")
        return f"| {d['doc_id']} | {d['effective_from']} | {d.get('date_source')} | {evidence} | {d['source_url']} | {check} |"

    counts = ", ".join(f"{k} {sum(d['date_source'] == k for d in dated)}" for k in REVIEWED)
    lines = [
        "# Corpus: effective dates (review)",
        "",
        "Generated by `make corpus-dates`. Chain: page text (letterhead, labelled, plain) -> w.e.f. anywhere -> URL or",
        "file name -> PDF metadata -> retrieval date (bank charge schedules only, meaning *current as of*).",
        "A seeded 10% per date_source is marked yes in the Check column: open the document and confirm. If wrong, correct",
        "`effective_from` in `manifest.yaml` and set `date_source: human`. Human and curated dates are never recomputed.",
        "",
        f"Dated: {counts}. To check: {len(sample)}. Needs review: {len(review)}. Needs a date: {len(undated)}.",
        "",
        "| doc_id | effective_from | date_source | Evidence | Source | Check |",
        "|---|---|---|---|---|---|",
        *[row(d, "**yes**" if d["doc_id"] in sample else "") for d in dated],
        "",
        "## Needs review: date before 1990 or after AS_OF_DATE (not counted)",
        "",
        "Confirm with `date_confirmed: true`, or correct the date and set `date_source: human`; then `make corpus-dates`.",
        "",
        "| doc_id | effective_from | date_source | Evidence | Source | Check |",
        "|---|---|---|---|---|---|",
        *[row(d) for d in review],
        "",
        "## No date found (not counted)",
        "",
        "Fill `effective_from` and `date_source: human` in `manifest.yaml`, then run `make corpus-dates`.",
        "",
        *([f"- {d['doc_id']}: {d['source_url']}" for d in undated] or ["- none"]),
    ]
    return "\n".join(lines) + "\n"
