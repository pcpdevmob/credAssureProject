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
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
import yaml

from .common import OUT, dumps_json, read_yaml, write_text
from .corpus import (
    CORPUS,
    OK,
    PENDING,
    USER_AGENT,
    Gate,
    audit,
    download,
    import_raw,
    tracked_files,
    verify,
)

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
DONE = OK | {"rejected_no_text"}


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


def links(page: str, base: str, pattern: str) -> list[tuple[str, str]]:
    """(absolute URL, anchor text) for same-host links matching ``pattern``, sorted, unique."""
    host = urlsplit(base).hostname
    seen: dict[str, str] = {}
    for href, inner in LINK.findall(page):
        href = html.unescape(href).strip()
        if href.lower().startswith(("javascript:", "mailto:", "#")) or not re.search(pattern, href):
            continue
        url = urljoin(base, href).replace(" ", "%20")
        if urlsplit(url).hostname != host or urlsplit(url).scheme != "https":
            continue
        text = " ".join(html.unescape(TAG.sub(" ", inner)).split())[:200]
        seen.setdefault(url, text or url.rsplit("/", 1)[-1])
    return sorted(seen.items())


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
        room = source["target"] - sum(
            1
            for d in docs
            if d["source"] == source["id"]
            and d["title"] != PENDING
            and lock.get(d["doc_id"], {}).get("status") != "rejected_no_text"
        )
        candidates: list[tuple[str, str]] = [
            (u, u.rsplit("/", 1)[-1] or u) for u in source.get("include_index", [])
        ]
        pager = source.get(
            "form_pages"
        )  # the site's own HTML form pager, e.g. {field: pageNo, last: 29}
        for index in source["index_urls"]:
            forms: list[dict[str, str] | None] = [None]
            if pager:
                forms += [{pager["field"]: str(n)} for n in range(2, pager["last"] + 1)]
            for form in forms:
                if len(candidates) >= room + len(urls & {u for u, _ in candidates}):
                    break
                page = gate.get(index, form)
                if isinstance(page, str) or page.status_code != 200:
                    break
                candidates += links(page.text, str(page.url), source["link_pattern"])
        for url, title in candidates:
            if room <= 0:
                break
            if url in urls:
                continue
            doc_id = _next_id(source["prefix"], ids)
            docs.append(_entry(source, doc_id, url, title))
            lock[doc_id] = {"source_url": url, "legal_basis": source["basis"], "status": "pending"}
            ids.add(doc_id)
            urls.add(url)
            room -= 1
            added += 1
        _drop_surplus_slots(source, manifest, lock)
    return added


def _drop_surplus_slots(
    source: dict[str, Any], manifest: dict[str, Any], lock: dict[str, dict[str, Any]]
) -> None:
    """Harvested documents replace unfilled slots, highest-numbered first."""
    docs = manifest["documents"]
    mine = [
        d
        for d in docs
        if d["source"] == source["id"]
        and lock.get(d["doc_id"], {}).get("status") != "rejected_no_text"
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
            and lock.get(d["doc_id"], {}).get("status") != "rejected_no_text"
        ]
        for k in range(len(live), source["target"]):
            doc_id = _next_id(source["prefix"], ids)
            index = source["index_urls"][k % len(source["index_urls"])]
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


def _todo(manifest: dict[str, Any], lock: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [d for d in manifest["documents"] if lock.get(d["doc_id"], {}).get("status") not in DONE]


def assign(items: list[dict[str, Any]], owners: int = 6) -> list[list[dict[str, Any]]]:
    """Split by host, cut hosts bigger than a fair share, then fill the lightest owner first."""
    by_host: dict[str, list[dict[str, Any]]] = {}
    for d in items:
        by_host.setdefault(urlsplit(d["source_url"]).hostname or "", []).append(d)
    share = max(1, -(-len(items) // owners))
    chunks = [
        group[i : i + share]
        for _, group in sorted(by_host.items())
        for i in range(0, len(group), share)
    ]
    sections: list[list[dict[str, Any]]] = [[] for _ in range(owners)]
    for chunk in sorted(chunks, key=len, reverse=True):
        min(sections, key=len).extend(chunk)
    return sections


def manual_markdown(manifest: dict[str, Any], lock: dict[str, dict[str, Any]]) -> str:
    items = _todo(manifest, lock)
    rejected = [
        d
        for d in manifest["documents"]
        if lock.get(d["doc_id"], {}).get("status") == "rejected_no_text"
    ]
    lines = [
        "# Corpus: documents to download by hand (ADR 0019)",
        "",
        "Generated by `make corpus-manual`. Do not edit by hand.",
        "",
        "## How to do it",
        "",
        "1. Open the link in a browser. Never use scripts, spoofed headers or headless browsers on these hosts.",
        "2. Save the file as `data/corpus/raw/<doc_id>.pdf` (or `.html` / `.htm`). The folder is gitignored; never commit it.",
        "3. **PENDING slot:** pick one document from the index page that is not in the manifest yet. In `data/corpus/manifest.yaml`,",
        "   fill `title`, `publisher`, `source_url` (the document's own URL), `effective_from`, `superseded_by`, `applies_to` and",
        "   `format`. For source 16, check `jurisdiction`.",
        "4. Run `make corpus-import`. A PDF with no text layer is rejected (no OCR), and a replacement slot appears here.",
        "5. Share the raw folder on the team drive; others run `make corpus-verify` to prove identical files.",
        "",
        f"**{len(items)} documents pending** across six owners.",
        "",
    ]
    for owner, section in zip(OWNERS, assign(items), strict=True):
        hosts = sorted({urlsplit(d["source_url"]).hostname or "" for d in section})
        lines += [
            f"## {owner}: {len(section)} documents ({', '.join(hosts)})",
            "",
            "| doc_id | Save as | Source | Link | Why manual |",
            "|---|---|---|---|---|",
        ]
        for d in sorted(section, key=lambda x: x["doc_id"]):
            record = lock.get(d["doc_id"], {})
            why = record.get("reason") or record.get("status", "pending")
            what = "pick from index" if d["title"] == PENDING else d["title"][:60].replace("|", "/")
            lines.append(
                f"| {d['doc_id']} | raw/{d['doc_id']}.{d['format']} | {d['source']}: {what} | {d['source_url']} | {why} |"
            )
        lines.append("")
    if rejected:
        lines += ["## Rejected (no text layer; replacement slots listed above)", ""]
        lines += [f"- {d['doc_id']}: {d['source_url']}" for d in rejected]
        lines.append("")
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
        "command", choices=["harvest", "download", "import", "verify", "manual", "report", "audit"]
    )
    command = parser.parse_args(argv).command
    sources, manifest, lock = load()
    import_errors: list[str] = []
    manual_hosts = set(sources["manual_hosts"])
    if command in {"harvest", "download"}:
        headers = {"User-Agent": USER_AGENT}
        with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
            gate = Gate(client, manual_hosts, time.sleep)
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
                )
                print(f"blocked hosts: {gate.blocked or 'none'}")
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
    if command in {"harvest", "download", "import", "manual"}:
        print(f"{ensure_slots(sources, manifest, lock)} manual slots added")
        save(manifest, lock)
        write_text(MANUAL, manual_markdown(manifest, lock))
    if command in {"report", "harvest", "download", "import"}:
        print(report(sources, manifest, lock, CORPUS / "text"))
    if command in {"audit", "import"}:
        errors, warnings = audit(manifest, tracked_files(), _synthetic())
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        statuses = [lock.get(d["doc_id"], {}).get("status") for d in manifest["documents"]]
        print(
            f"{len(statuses)} manifest entries: {sum(x in OK for x in statuses)} available, "
            f"{statuses.count('rejected_no_text')} rejected (no text), "
            f"{len(statuses) - sum(x in OK for x in statuses) - statuses.count('rejected_no_text')} pending; "
            f"{_synthetic()} synthetic; {len(errors)} errors, {len(warnings)} warnings"
        )
        return 1 if errors or (command == "import" and import_errors) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
