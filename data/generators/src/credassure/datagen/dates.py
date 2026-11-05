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

from pypdf import PdfReader

from .common import rng
from .corpus import OK, extract_text

EARLIEST, LATEST = date(1990, 1, 1), date(2027, 12, 31)
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


def apply_dates(
    manifest: dict[str, Any], lock: dict[str, dict[str, Any]], raw_dir: Path
) -> tuple[int, int, int]:
    """Date every available document. Returns (extracted, needs_date, promoted back)."""
    extracted = undated = promoted = 0
    for d in manifest["documents"]:
        record = lock.get(d["doc_id"], {})
        status = record.get("status")
        if status == "needs_date" and not d.get("effective_from"):
            raw = raw_dir / record.get("raw_file", "")
            retrieved = record.get("retrieved_on")
            ignore = date.fromisoformat(str(retrieved)) if retrieved else None
            hit = candidate_date(first_pages(raw, d["format"]), ignore) if raw.is_file() else None
            if hit is not None:
                d["effective_from"], d["date_source"] = hit[0].isoformat(), "extracted"
                record["date_evidence"] = hit[1]
                record["status"] = record.pop("status_before_date", "ok")
                extracted += 1
            continue
        if status == "needs_date" and d.get("effective_from"):
            record["status"] = record.pop("status_before_date", "ok")
            d.setdefault("date_source", "human")
            promoted += 1
            continue
        if status not in OK or (d.get("effective_from") and d.get("date_source") != "extracted"):
            continue
        raw = raw_dir / record.get("raw_file", "")
        retrieved = record.get("retrieved_on")
        ignore = date.fromisoformat(str(retrieved)) if retrieved else None
        hit = candidate_date(first_pages(raw, d["format"]), ignore) if raw.is_file() else None
        if hit is None:
            d["effective_from"] = None
            d.pop("date_source", None)
            record["status_before_date"] = status
            record["status"] = "needs_date"
            undated += 1
            continue
        d["effective_from"] = hit[0].isoformat()
        d["date_source"] = "extracted"
        record["date_evidence"] = hit[1]
        extracted += 1
    return extracted, undated, promoted


def review_markdown(manifest: dict[str, Any], lock: dict[str, dict[str, Any]]) -> str:
    extracted = sorted(
        (d for d in manifest["documents"] if d.get("date_source") == "extracted"),
        key=lambda d: d["doc_id"],
    )
    sample = (
        set(
            rng("date-review").sample(
                [d["doc_id"] for d in extracted], math.ceil(len(extracted) / 10)
            )
        )
        if extracted
        else set()
    )
    undated = sorted(
        d["doc_id"]
        for d in manifest["documents"]
        if lock.get(d["doc_id"], {}).get("status") == "needs_date"
    )
    lines = [
        "# Corpus: extracted effective dates (review)",
        "",
        "Generated by `make corpus-dates`. A seeded 10% sample is marked **check: yes**: open the document, confirm the",
        "date, and if it is wrong, correct `effective_from` in `manifest.yaml` and set `date_source: human`.",
        "",
        f"{len(extracted)} extracted, {len(sample)} to check, {len(undated)} need a date by hand.",
        "",
        "| doc_id | effective_from | Evidence | Source | Check |",
        "|---|---|---|---|---|",
    ]
    for d in extracted:
        evidence = lock.get(d["doc_id"], {}).get("date_evidence", "").replace("|", "/")
        check = "**yes**" if d["doc_id"] in sample else ""
        lines.append(
            f"| {d['doc_id']} | {d['effective_from']} | {evidence} | {d['source_url']} | {check} |"
        )
    lines += [
        "",
        "## No date found (not counted as available until dated)",
        "",
        "Fill `effective_from` and `date_source: human` in `manifest.yaml`, then run `make corpus-dates`.",
        "",
    ]
    lines += [f"- {doc_id}" for doc_id in undated] or ["- none"]
    return "\n".join(lines) + "\n"
