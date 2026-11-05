"""Grow the real Indian corpus toward 500 or more documents (ADR 0019, ``data/corpus/sources.yaml``).

- ``harvest``: for ``method: script`` sources, reads each index page through ``Gate`` (robots.txt,
  one request per second, host stopped on a block) and appends same-host document links matching
  ``link_pattern``, sorted, up to the source's target. The manifest is append-only by doc_id, so
  entries an owner edited are never overwritten.
- ``ensure_slots``: tops every source up to its target with ``PENDING`` slots. A rejected no-text
  PDF does not count, so it gets a replacement slot. Owners fill a slot in ``manifest.yaml`` when
  they save its file.
- ``manual_markdown``: writes ``MANUAL_DOWNLOADS.md`` in six owner sections of similar size,
  keeping a host with one owner where possible.
- ``report``: per source, real planned / available / manual pending. "Available" means status
  ``ok`` or ``ok_manual`` and the extracted text file exists.

CLI: ``python -m credassure.datagen.harvest {harvest,download,import,verify,manual,report,audit}``.
"""

import argparse
import html
import json
import re
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
import yaml

from .common import OUT, dumps_json, read_yaml, user_agent, write_text
from .corpus import (
    CORPUS,
    DROPPED,
    OK,
    PENDING,
    Gate,
    audit,
    download,
    extract_text,
    import_raw,
    retryable,
    tracked_files,
    verify,
)
from .dates import apply_dates, candidate_date, review_markdown, url_date
from .export import export

MANIFEST = CORPUS / "manifest.yaml"
LOCK = CORPUS / "manifest.lock.json"
SOURCES = CORPUS / "sources.yaml"
MANUAL = CORPUS / "MANUAL_DOWNLOADS.md"
OWNERS = [f"[Name {i}]" for i in range(1, 7)]
LINK = re.compile(r'<a\b[^>]*?href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
TAG = re.compile(r"<[^>]+>")
DMY = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d{2})\b")
ISO = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
HEADER = (
    "# Real Indian corpus manifest (ADR 0019). Written by `make corpus-harvest` (append-only by doc_id).\n"
    "# Owners fill PENDING slots in place when they save a file to data/corpus/raw/ (see MANUAL_DOWNLOADS.md).\n"
    "# legal_basis L1-L4 only; jurisdiction IN or IN-XX; applies_to commercial_bank|nbfc|sfb|coop_bank|all.\n"
)
DONE = OK | DROPPED | {"needs_date", "needs_review"}
# Priority tiers for owners (owner decision 6): T1 RBI Master Directions, RBI FAQs/rates/press releases,
# CGTMSE replacements, Parliament answers; T2 NCGTC; T3 judgments; T4 state policies; T5 Gazette; T6 rest.
TIER = {1: 1, 3: 1, 4: 1, 14: 1, 5: 2, 15: 3, 16: 4, 8: 5}
RETRY_WAIT = timedelta(hours=24)
RULES = [
    "## Placeholder-selection rules",
    "",
    "- Relevant to MSME credit, credit guarantees, KFS / loan disclosure, interest rates, payments to MSEs or GST on loan fees.",
    "- Not already in the manifest (import rejects a file whose SHA-256 matches another document).",
    "- One file of at most 20 MB, with a text layer (scans are rejected; there is no OCR).",
    "- CGTMSE replacements: prefer text-layer circulars from 2015 onward.",
    "- **RBI pages (rows marked HTML, listed first):** save the page in the browser as *Web page, HTML only* to",
    "  `data/corpus/raw/<doc_id>.html`. Do not look for the PDF: HTML always has text, so it can never be rejected as a scan.",
    "- In `manifest.yaml` fill `title`, `source_url` (the document itself), `effective_from`, `applies_to` and `jurisdiction`",
    "  (and `superseded_by` for an RBI circular replaced by the 2025 consolidation).",
    "",
]


def load() -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    lock = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}
    return read_yaml(SOURCES), read_yaml(MANIFEST), lock


def save(manifest: dict[str, Any], lock: dict[str, dict[str, Any]]) -> None:
    write_text(
        MANIFEST, HEADER + yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120)
    )
    write_text(LOCK, dumps_json(lock))


def _date(text: str) -> str | None:
    if m := ISO.search(text):
        return f"{m[1]}-{m[2]}-{m[3]}"
    if m := DMY.search(text):
        day, month, year = int(m[1]), int(m[2]), int(m[3])
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def _next_id(prefix: str, ids: set[str]) -> str:
    n = 1
    while f"{prefix}-{n:03d}" in ids:
        n += 1
    return f"{prefix}-{n:03d}"


def _entry(
    source: dict[str, Any], doc_id: str, url: str, title: str, slot_no: int = 0
) -> dict[str, Any]:
    states = source["jurisdiction"]
    return {
        "doc_id": doc_id,
        "tag": source["prefix"].lower(),
        "collection": "public",
        "jurisdiction": states[slot_no % len(states)],
        "legal_basis": source["basis"],
        "format": "pdf" if ".pdf" in url.lower() else "html",
        "title": title,
        "publisher": PENDING if title == PENDING else (urlsplit(url).hostname or ""),
        "effective_from": None if title == PENDING else _date(f"{title} {url}"),
        "superseded_by": None,
        "source_url": url,
        "source": source["id"],
        "applies_to": source["applies_to"],
        "method": "manual" if title == PENDING else "script",
    }


FY = re.compile(r"\b((?:19|20)\d{2})\s*[-\u2013]\s*\d{2}\b")
YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
TR_OPEN, TR_CLOSE = re.compile(r"<tr\b", re.I), re.compile(r"</tr>", re.I)


def links(page: str, base: str, pattern: str, context: bool = False) -> list[tuple[str, str]]:
    """(absolute URL, text) for same-host links matching ``pattern``, sorted, unique. With
    ``context``, the text is the enclosing table row (a CGTMSE row shows its number, year and date)."""
    host = urlsplit(base).hostname
    seen: dict[str, str] = {}
    for m in LINK.finditer(page):
        href, inner = html.unescape(m.group(1)).strip(), m.group(2)
        if href.lower().startswith(("javascript:", "mailto:", "#")) or not re.search(pattern, href):
            continue
        url = urljoin(base, href).replace(" ", "%20")
        if urlsplit(url).hostname != host or urlsplit(url).scheme != "https":
            continue
        if context:
            opens = [t.start() for t in TR_OPEN.finditer(page, 0, m.start())]
            close = TR_CLOSE.search(page, m.end())
            if opens and close and not TR_CLOSE.search(page, opens[-1], m.start()):
                inner = page[opens[-1] : close.end()]
        text = " ".join(html.unescape(TAG.sub(" ", inner)).split())[:300]
        seen.setdefault(url, text or url.rsplit("/", 1)[-1])
    return sorted(seen.items())


def visible_year(text: str) -> int | None:
    """Year shown next to a link: a date, else a financial year (139/2017-18), else a plain year."""
    if hit := candidate_date(text):
        return hit[0].year
    if m := FY.search(text):
        return int(m.group(1))
    if m := YEAR.search(text):
        return int(m.group(1))
    return None


def harvest(
    sources: dict[str, Any], manifest: dict[str, Any], lock: dict[str, dict[str, Any]], gate: Gate
) -> int:
    """Append script-harvested entries. Returns how many were added."""
    docs = manifest["documents"]
    ids = {d["doc_id"] for d in docs}
    urls = {d["source_url"] for d in docs}
    added = 0
    for source in sources["sources"]:
        if source["method"] != "script":
            continue
        room = (
            source["target"]
            + source.get("buffer", 0)
            - sum(
                1
                for d in docs
                if d["source"] == source["id"]
                and d["title"] != PENDING
                and lock.get(d["doc_id"], {}).get("status") not in DROPPED
            )
        )
        min_date = date.fromisoformat(source["min_date"]) if source.get("min_date") else None
        candidates: list[tuple[str, str]] = [
            (u, u.rsplit("/", 1)[-1] or u) for u in source.get("include_index", [])
        ]
        fresh = 0
        for entry in source["index_urls"]:
            index, pattern, pager = _index(entry, source)
            follow = entry.get("follow") if isinstance(entry, dict) else None
            forms: list[dict[str, str] | None] = [None]
            if pager:
                forms += [{pager["field"]: str(n)} for n in range(2, pager["last"] + 1)]
            for form in forms:
                if fresh >= room:
                    break
                page = gate.get(index, form)
                if isinstance(page, str) or page.status_code != 200:
                    break
                found = links(page.text, str(page.url), pattern, context=min_date is not None)
                if follow:  # second level: index -> edition pages -> documents (sidbi.in)
                    found += _follow(page, follow, pattern, gate)
                for url, text in found:
                    year = visible_year(text) if min_date else None
                    if min_date and year is not None and year < min_date.year:
                        continue  # visibly older than min_date: never harvested
                    candidates.append((url, text))
                    fresh += url not in urls
        if min_date:  # newest first, so the buffer fills with recent circulars
            candidates.sort(key=lambda c: -(visible_year(c[1]) or 0))
        for url, title in candidates:
            if room <= 0:
                break
            if url in urls:
                continue
            doc_id = _next_id(source["prefix"], ids)
            docs.append(_entry(source, doc_id, url, title))
            lock[doc_id] = {"source_url": url, "legal_basis": source["basis"], "status": "pending"}
            if (
                min_date and visible_year(title) is None
            ):  # no year shown: check the date on download
                lock[doc_id]["date_gate"] = min_date.isoformat()
            ids.add(doc_id)
            urls.add(url)
            room -= 1
            added += 1
        _drop_surplus_slots(source, manifest, lock)
    return added


def _follow(page: httpx.Response, follow: str, pattern: str, gate: Gate) -> list[tuple[str, str]]:
    """Edition pages linked from ``page`` (and from an all-editions page it links), then their documents."""
    queue = [u for u, _ in links(page.text, str(page.url), follow)]
    seen, docs = set(queue), []
    while queue:
        sub = gate.get(queue.pop(0))
        if isinstance(sub, str) or sub.status_code != 200:
            continue
        docs += links(sub.text, str(sub.url), pattern)
        for u, _ in links(sub.text, str(sub.url), follow):
            if u not in seen:
                seen.add(u)
                queue.append(u)
    return docs


def _index(
    entry: str | dict[str, Any], source: dict[str, Any]
) -> tuple[str, str, dict[str, Any] | None]:
    """(url, link pattern, form pager). A plain URL uses the source's pattern and pager (e.g. the
    site's own HTML form pager {field: pageNo, last: 29}); a {url, pattern, form_pages} entry overrides."""
    if isinstance(entry, str):
        return entry, source.get("link_pattern", ""), source.get("form_pages")
    return (
        entry["url"],
        entry.get("pattern", source.get("link_pattern", "")),
        entry.get("form_pages"),
    )


CURATED = CORPUS / "manual_curated.yaml"


def _norm(url: str) -> str:
    parts = urlsplit(url)
    host = (parts.hostname or "").removeprefix("www.")
    return f"{host}{parts.path}?{parts.query}".rstrip("?").lower()


def curate(
    sources: dict[str, Any],
    manifest: dict[str, Any],
    lock: dict[str, dict[str, Any]],
    items: list[dict[str, Any]],
) -> int:
    """Turn curated documents (exact URL or named recipe) into manual entries: fill the source's
    PENDING slots first, then append; never duplicate a URL or a title already in the manifest."""
    docs = manifest["documents"]
    by_id = {s["id"]: s for s in sources["sources"]}
    ids = {d["doc_id"] for d in docs}
    have = {_norm(d["source_url"]) for d in docs if d["title"] != PENDING}
    titles = {d["title"] for d in docs}
    added = 0
    for item in items:
        if item["title"] in titles or (item["kind"] == "exact" and _norm(item["url"]) in have):
            continue
        source = by_id[item["source"]]
        slots = sorted(
            (d for d in docs if d["source"] == source["id"] and d["title"] == PENDING),
            key=lambda d: d["doc_id"],
        )
        if slots:
            doc = slots[0]
        else:
            doc = _entry(source, _next_id(source["prefix"], ids), item["url"], PENDING)
            docs.append(doc)
            ids.add(doc["doc_id"])
        doc.update(
            title=item["title"],
            source_url=item["url"],
            applies_to=item["applies_to"],
            jurisdiction=item["jurisdiction"],
            method="manual",
            effective_from=None,
            format="pdf" if ".pdf" in item["url"].lower() else "html",
            publisher=urlsplit(item["url"]).hostname or "",
        )
        record = lock.setdefault(doc["doc_id"], {})
        record.update(
            source_url=item["url"],
            legal_basis=source["basis"],
            status="pending_manual",
            reason=item.get("recipe") or "exact document: open the link and save it",
        )
        have.add(_norm(item["url"]))
        titles.add(item["title"])
        added += 1
    for source in sources["sources"]:
        _drop_surplus_slots(source, manifest, lock)
    return added


def home_page_rows(
    sources: dict[str, Any], manifest: dict[str, Any], lock: dict[str, dict[str, Any]]
) -> list[str]:
    """Manual rows that point at a bare home page without a recipe (must be empty)."""
    recipes = {s["id"] for s in sources["sources"] if s.get("manual_recipe")}
    return [
        d["doc_id"]
        for d in _todo(manifest, lock)
        if urlsplit(d["source_url"]).path in {"", "/"} and d["source"] not in recipes
    ]


def _drop_surplus_slots(
    source: dict[str, Any], manifest: dict[str, Any], lock: dict[str, dict[str, Any]]
) -> None:
    """Harvested documents replace unfilled slots, highest-numbered first."""
    docs = manifest["documents"]
    mine = [
        d
        for d in docs
        if d["source"] == source["id"] and lock.get(d["doc_id"], {}).get("status") not in DROPPED
    ]
    surplus = len(mine) - source["target"]
    slots = sorted(
        (d for d in mine if d["title"] == PENDING), key=lambda d: d["doc_id"], reverse=True
    )
    for d in slots[: max(0, surplus)]:
        docs.remove(d)
        lock.pop(d["doc_id"], None)


def ensure_slots(
    sources: dict[str, Any], manifest: dict[str, Any], lock: dict[str, dict[str, Any]]
) -> int:
    """Top each source up to its target with PENDING manual slots (rejected docs need a replacement)."""
    docs = manifest["documents"]
    ids = {d["doc_id"] for d in docs}
    added = 0
    for source in sources["sources"]:
        live = [
            d
            for d in docs
            if d["source"] == source["id"]
            and lock.get(d["doc_id"], {}).get("status") not in DROPPED
        ]
        for k in range(len(live), source["target"]):
            doc_id = _next_id(source["prefix"], ids)
            index = _index(source["index_urls"][k % len(source["index_urls"])], source)[0]
            docs.append(_entry(source, doc_id, index, PENDING, slot_no=k))
            lock[doc_id] = {
                "source_url": index,
                "legal_basis": source["basis"],
                "status": "pending_manual",
                "reason": "manual source"
                if source["method"] == "manual"
                else "beyond what the script could reach",
            }
            ids.add(doc_id)
            added += 1
    return added


ACCESS = ("allowed", "restricted", "unknown")


def ensure_hosts(manifest: dict[str, Any]) -> int:
    """Add every host in the manifest to its ``hosts`` terms map as ``unknown``; never overwrite."""
    hosts = manifest.setdefault("hosts", {})
    added = 0
    for d in manifest["documents"]:
        host = urlsplit(d["source_url"]).hostname or ""
        if host and host not in hosts:
            hosts[host] = {"terms_url": None, "terms_note": None, "automated_access": "unknown"}
            added += 1
    manifest["hosts"] = dict(sorted(hosts.items()))
    return added


def restricted_hosts(manifest: dict[str, Any]) -> set[str]:
    return {
        h for h, t in manifest.get("hosts", {}).items() if t.get("automated_access") == "restricted"
    }


def hosts_missing_terms(manifest: dict[str, Any], lock: dict[str, dict[str, Any]]) -> list[str]:
    """Rows for MANUAL_DOWNLOADS.md: hosts whose terms of use nobody has recorded yet."""
    rows: list[str] = []
    for host, terms in sorted(manifest.get("hosts", {}).items()):
        if terms.get("terms_url") and terms.get("terms_note"):
            continue
        docs = [d for d in manifest["documents"] if urlsplit(d["source_url"]).hostname == host]
        owners = [
            str(lock[d["doc_id"]]["owner"]) for d in docs if lock.get(d["doc_id"], {}).get("owner")
        ]
        owner = (
            max(sorted(set(owners)), key=owners.count)
            if owners
            else OWNERS[len(rows) % len(OWNERS)]
        )
        rows.append(
            f"| {host} | {len(docs)} | {owner} | {terms.get('automated_access', 'unknown')} |"
        )
    if not rows:
        return []
    return [
        "## Hosts missing terms of use (ADR 0020)",
        "",
        "Open the host's terms of use / copyright / hyperlinking policy page and fill, in `data/corpus/manifest.yaml`",
        "under `hosts:`, `terms_url`, `terms_note` (does it allow automated access? any reuse limits?) and",
        "`automated_access: allowed | restricted`. A `restricted` host is never fetched by script again.",
        "",
        "| Host | Documents | Owner | automated_access |",
        "|---|---|---|---|",
        *rows,
        "",
    ]


def _todo(manifest: dict[str, Any], lock: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Manual work only. Not listed: the script's own download queue (status ``pending``) and
    documents on a host still waiting for its one-time retry (ADR 0020)."""
    waiting = {
        k[5:]
        for k, v in lock.items()
        if k.startswith("host:") and v.get("retry_after") and not v.get("retry_outcome")
    }
    return [
        d
        for d in manifest["documents"]
        if lock.get(d["doc_id"], {}).get("status") not in DONE | {"pending"}
        and urlsplit(d["source_url"]).hostname not in waiting
    ]


RBI_HTML = re.compile(
    r"(?:BS_ViewMasDirections|NotificationUser|FS_FAQs|BS_PressReleaseDisplay)", re.I
)


def rbi_html(doc: dict[str, Any]) -> bool:
    """An RBI page owners save as HTML: those URL types, and Master Direction slots (source 1),
    whose documents are BS_ViewMasDirections pages."""
    host = urlsplit(doc["source_url"]).hostname or ""
    return host.endswith("rbi.org.in") and (
        bool(RBI_HTML.search(doc["source_url"])) or doc["source"] == 1
    )


def tier(doc: dict[str, Any]) -> int:
    return TIER.get(doc["source"], 6)


def assign_owners(items: list[dict[str, Any]], lock: dict[str, dict[str, Any]]) -> None:
    """Stable owners: keep existing ones; give new items to owners tier by tier, lightest first,
    keeping a host's items together within a tier unless it exceeds that tier's fair share."""
    load = {o: 0 for o in OWNERS}
    for d in items:
        owner = lock.get(d["doc_id"], {}).get("owner")
        if owner in load:
            load[owner] += 1
    new = [d for d in items if lock.get(d["doc_id"], {}).get("owner") not in load]
    for level in sorted({tier(d) for d in new}):
        group = [d for d in new if tier(d) == level]
        by_host: dict[str, list[dict[str, Any]]] = {}
        for d in sorted(group, key=lambda x: x["doc_id"]):
            by_host.setdefault(urlsplit(d["source_url"]).hostname or "", []).append(d)
        share = max(1, -(-len(group) // len(OWNERS)))
        chunks = [
            h[i : i + share] for _, h in sorted(by_host.items()) for i in range(0, len(h), share)
        ]
        for chunk in sorted(chunks, key=len, reverse=True):
            owner = min(OWNERS, key=lambda o: (load[o], OWNERS.index(o)))
            for d in chunk:
                lock.setdefault(d["doc_id"], {})["owner"] = owner
            load[owner] += len(chunk)


GENERIC = {"", "manual source", "beyond what the script could reach"}


def manual_markdown(
    manifest: dict[str, Any], lock: dict[str, dict[str, Any]], sources: dict[str, Any] | None = None
) -> str:
    recipes = {s["id"]: s for s in (sources or {}).get("sources", []) if s.get("manual_recipe")}
    items = _todo(manifest, lock)
    assign_owners(items, lock)
    rejected = [
        d for d in manifest["documents"] if lock.get(d["doc_id"], {}).get("status") in DROPPED
    ]
    lines = [
        "# Corpus: documents to download by hand (ADR 0019)",
        "",
        "Generated by `make corpus-manual`. Do not edit by hand. Each section starts with priority sources (T1).",
        "",
        "## How to do it",
        "",
        "1. Open the link in a browser. Never use scripts, spoofed headers or headless browsers on these hosts.",
        "2. Save the file as `data/corpus/raw/<doc_id>.pdf` (or `.html` / `.htm`). The folder is gitignored; never commit it.",
        "3. **PENDING slot:** pick one document from the index page by the rules below, then fill its entry in `data/corpus/manifest.yaml`.",
        "4. Run `make corpus-import` (it also extracts the date). Rejected scans get a replacement slot here.",
        "5. Share the raw folder on the team drive; others run `make corpus-verify` to prove identical files.",
        "",
        *RULES,
        "Tiers: T1 RBI Master Directions, RBI FAQs/rates/press releases, CGTMSE replacements, Parliament answers; "
        "T2 NCGTC; T3 judgments; T4 state policies; T5 Gazette; T6 others.",
        "",
        *(
            [
                "## Recipes",
                "",
                "Rows marked **Recipe N** have no single link. Follow the recipe for source N, save the document as",
                "`raw/<doc_id>.<pdf|html>`, and fill `title`, `source_url` (the document's own URL), `applies_to` and `jurisdiction`",
                "for that doc_id in `manifest.yaml`.",
                "",
            ]
            + [
                f"- **Recipe {i} - {s['name']}:** {s['manual_recipe']}"
                for i, s in sorted(recipes.items())
            ]
            + [""]
            if recipes
            else []
        ),
        f"**{len(items)} documents pending** across six owners.",
        "",
    ]
    for owner in OWNERS:
        section = sorted(
            (d for d in items if lock[d["doc_id"]]["owner"] == owner),
            key=lambda d: (not rbi_html(d), tier(d), d["doc_id"]),
        )
        hosts = sorted({urlsplit(d["source_url"]).hostname or "" for d in section})
        lines += [
            f"## {owner}: {len(section)} documents ({', '.join(hosts)})",
            "",
            "| Tier | doc_id | Save as | Source | Link | Why manual |",
            "|---|---|---|---|---|---|",
        ]
        for d in section:
            record = lock.get(d["doc_id"], {})
            why = record.get("reason") or record.get("status", "pending")
            if d["title"] == PENDING and d["source"] in recipes:
                why = f"**Recipe {d['source']}** (see Recipes above)"
            elif not rbi_html(d) and why in GENERIC | {"exact document: open the link and save it"}:
                how = "save the PDF" if d["format"] == "pdf" else "save as *Web page, HTML only*"
                why = f"exact document: open the link and {how}"
            if rbi_html(d) and not (d["title"] == PENDING and d["source"] in recipes):
                note = record.get("reason", "")
                extra = (
                    ""
                    if note in {"", "manual source", "beyond what the script could reach"}
                    else f". {note}"
                )
                why = "**HTML:** save as *Web page, HTML only*; do not look for the PDF" + extra
            what = "pick from index" if d["title"] == PENDING else d["title"][:60].replace("|", "/")
            if d["source"] == 4 and d["title"] == PENDING:
                what += " (text-layer circular from 2015 onward)"
            lines.append(
                f"| T{tier(d)} | {d['doc_id']} | raw/{d['doc_id']}.{'pdf or .html' if d['title'] == PENDING and d['source'] in recipes else 'html' if rbi_html(d) else d['format']} | {d['source']}: {what} | {d['source_url']} | {why} |"
            )
        lines.append("")
    lines += hosts_missing_terms(manifest, lock)
    if rejected:
        lines += ["## Rejected (no text layer; replacement slots listed above)", ""]
        lines += [f"- {d['doc_id']}: {d['source_url']}" for d in rejected]
        lines.append("")
    return "\n".join(lines)


def gate_date(body: bytes, fmt: str, url: str) -> date | None:
    """Date for a download gate: page text first, then the URL."""
    hit = candidate_date(extract_text(body, fmt)[:6000]) or url_date(url)
    return hit[0] if hit else None


def prepare_hosts(lock: dict[str, dict[str, Any]], gate: Gate, now: datetime) -> frozenset[str]:
    """Pre-block hosts waiting for their retry or already retried. Returns hosts due their one retry."""
    due: set[str] = set()
    for key, record in lock.items():
        if not key.startswith("host:"):
            continue
        host = key[5:]
        if record.get("retry_outcome"):
            gate.blocked[host] = f"manual: {record['reason']}"
        elif now < datetime.fromisoformat(record["retry_after"]):
            gate.blocked[host] = f"retry after {record['retry_after']}"
        else:
            due.add(host)
    return frozenset(due)


def record_hosts(
    lock: dict[str, dict[str, Any]], gate: Gate, due: frozenset[str], now: datetime
) -> None:
    """Record each due host's one retry, and every new host failure with its retry rule."""
    stamp = now.isoformat(timespec="seconds")
    for host in due:
        outcome = (
            f"failed: {gate.blocked[host]}"
            if host in gate.blocked
            else f"ok: {gate.fetched.get(host, 0)} fetched"
        )
        lock[f"host:{host}"] |= {"retry_outcome": outcome, "retried_at": stamp}
    for host, reason in gate.blocked.items():
        key = f"host:{host}"
        if key in lock or reason.startswith(("manual:", "retry after")):
            continue
        record: dict[str, Any] = {"reason": reason, "first_failure": stamp}
        if retryable(reason):
            record["retry_after"] = (now + RETRY_WAIT).isoformat(timespec="seconds")
        else:
            record["retry_outcome"] = "not retried (permanent)"
        lock[key] = record


def status_screen(
    sources: dict[str, Any],
    manifest: dict[str, Any],
    lock: dict[str, dict[str, Any]],
    text_dir: Path,
) -> str:
    def counts(docs: list[dict[str, Any]]) -> tuple[int, int, int, int]:
        st = [lock.get(d["doc_id"], {}).get("status") for d in docs]
        avail = sum(
            1
            for d, x in zip(docs, st, strict=True)
            if x in OK and (text_dir / f"{d['doc_id']}.txt").exists()
        )
        return (
            avail,
            sum(x not in DONE for x in st),
            sum(x in DROPPED for x in st),
            st.count("needs_date") + st.count("needs_review"),
        )

    docs = manifest["documents"]
    avail, pending, rejected, undated = counts(docs)
    bar = "#" * min(50, avail // 10) + "." * max(0, 50 - avail // 10)
    lines = [
        f"Real available {avail}/500 [{bar}] {max(0, 500 - avail)} to go",
        f"Pending {pending} | rejected (no text) {rejected} | needs date or review {undated}",
        "",
        f"{'src':>3} {'tgt+buf':>7} {'avail':>5} {'pend':>5} {'rej':>4} {'nodate':>6}  name",
    ]
    for s in sources["sources"]:
        a, p, r, u = counts([d for d in docs if d["source"] == s["id"]])
        tb = f"{s['target']}+{s.get('buffer', 0)}"
        lines.append(f"{s['id']:>3} {tb:>7} {a:>5} {p:>5} {r:>4} {u:>6}  {s['name'][:46]}")
    lines += ["", f"{'owner':<10} {'assigned':>8} {'imported':>8} {'pending':>7}"]
    for owner in OWNERS:
        mine = [d for d in docs if lock.get(d["doc_id"], {}).get("owner") == owner]
        st = [lock[d["doc_id"]].get("status") for d in mine]
        lines.append(
            f"{owner:<10} {len(mine):>8} {st.count('ok_manual'):>8} {sum(x not in DONE for x in st):>7}"
        )
    return "\n".join(lines)


def report(
    sources: dict[str, Any],
    manifest: dict[str, Any],
    lock: dict[str, dict[str, Any]],
    text_dir: Path,
) -> str:
    todo = {d["doc_id"] for d in _todo(manifest, lock)}
    rows = [
        "| # | Source | Real planned | Real available | Manual pending | Basis | Agents |",
        "|---|---|---|---|---|---|---|",
    ]
    total_planned = total_available = total_pending = 0
    for s in sources["sources"]:
        docs = [d for d in manifest["documents"] if d["source"] == s["id"]]
        available = sum(
            1
            for d in docs
            if lock.get(d["doc_id"], {}).get("status") in OK
            and (text_dir / f"{d['doc_id']}.txt").exists()
        )
        pending = sum(1 for d in docs if d["doc_id"] in todo)
        rows.append(
            f"| {s['id']} | {s['name']} | {s['target']} | {available} | {pending} | {s['basis']} | "
            f"{', '.join(s['agents'])} |"
        )
        total_planned += s["target"]
        total_available += available
        total_pending += pending
    rows.append(
        f"| | **Total real** | **{total_planned}** | **{total_available}** | **{total_pending}** | | |"
    )
    gap = max(0, 500 - total_available)
    rows += [
        "",
        f"Real available: **{total_available}**. Distance to 500: **{gap}**. "
        "Synthetic KFS and policies are extra and not counted (ADR 0019).",
    ]
    return "\n".join(rows)


def _synthetic() -> int:
    return sum(1 for folder in ("kfs", "policies") for _ in (OUT / folder).glob("*.md"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m credassure.datagen.harvest")
    parser.add_argument(
        "command",
        choices=[
            "harvest",
            "download",
            "import",
            "verify",
            "manual",
            "report",
            "audit",
            "dates",
            "status",
            "export",
            "curate",
        ],
    )
    command = parser.parse_args(argv).command
    sources, manifest, lock = load()
    import_errors: list[str] = []
    manual_hosts = set(sources["manual_hosts"])
    if command in {"harvest", "download"}:
        headers = {"User-Agent": user_agent()}  # contactable sender, from settings (ADR 0020)
        print(
            "Notice (ADR 0020): run corpus fetches from a personal machine and network, not an employer network."
        )
        with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
            gate = Gate(client, manual_hosts, time.sleep, restricted_hosts(manifest))
            now = datetime.now(UTC)
            due = prepare_hosts(lock, gate, now)
            if command == "harvest":
                print(
                    f"{harvest(sources, manifest, lock, gate)} entries harvested; blocked: {gate.blocked or 'none'}"
                )
            else:
                download(
                    manifest["documents"],
                    lock,
                    CORPUS,
                    gate,
                    date.today(),
                    lambda: save(manifest, lock),
                    retry_hosts=due,
                    gate_date=gate_date,
                )
                print(f"blocked hosts: {gate.blocked or 'none'}")
            record_hosts(lock, gate, due, now)
    if command == "import":
        import_errors = import_raw(manifest["documents"], lock, CORPUS, date.today())
        for error in import_errors:
            print(f"ERROR {error}", file=sys.stderr)
    if command == "verify":
        same, missing, bad = verify(lock, CORPUS / "raw")
        print(f"{len(same)} identical, {len(missing)} missing, {len(bad)} mismatched")
        for doc_id in bad:
            print(f"MISMATCH {doc_id}", file=sys.stderr)
        return 1 if bad or missing else 0  # a teammate must hold every file to prove the sync
    if command == "curate":
        items = read_yaml(CURATED)["items"]
        print(f"{curate(sources, manifest, lock, items)} curated documents placed")
    if command in {"download", "import", "dates"}:
        chained, undated, review = apply_dates(manifest, lock, CORPUS / "raw", CORPUS / "text")
        print(f"dates: {chained} dated by the chain, {undated} need a date, {review} need review")
        write_text(CORPUS / "DATE_REVIEW.md", review_markdown(manifest, lock))
    if command == "status":
        print(status_screen(sources, manifest, lock, CORPUS / "text"))
    if command in {"status", "export"}:
        result = export(sources, manifest, lock, CORPUS)
        print(
            f"wrote CORPUS_INDEX.md and CORPUS_INDEX.xlsx: {result['available']}/500 real available"
        )
        return 0
    if command in {"harvest", "download", "import", "manual", "dates", "curate"}:
        print(f"{ensure_slots(sources, manifest, lock)} manual slots added")
        ensure_hosts(manifest)
        write_text(MANUAL, manual_markdown(manifest, lock, sources))  # assigns owners into the lock
        save(manifest, lock)
    if command in {"report", "harvest", "download", "import"}:
        print(report(sources, manifest, lock, CORPUS / "text"))
    if command in {"audit", "import"}:
        errors, warnings = audit(manifest, tracked_files(), _synthetic(), lock)
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        statuses = [lock.get(d["doc_id"], {}).get("status") for d in manifest["documents"]]
        print(
            f"{len(statuses)} manifest entries: {sum(x in OK for x in statuses)} available, "
            f"{sum(x in DROPPED for x in statuses)} dropped (scans, pre-2015), "
            f"{len(statuses) - sum(x in OK for x in statuses) - sum(x in DROPPED for x in statuses)} pending; "
            f"{_synthetic()} synthetic; {len(errors)} errors, {len(warnings)} warnings"
        )
        return 1 if errors or (command == "import" and import_errors) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
