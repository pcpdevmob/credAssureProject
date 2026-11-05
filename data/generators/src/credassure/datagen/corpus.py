"""Public corpus tooling (scope #14, BRD §10, docs/data/DATA_RESOURCES.md).

``audit``: every manifest entry has a canonical doc_id, https URL, legal basis L1-L6,
jurisdiction and an ``effective_from`` key (null means "confirm on the page", a warning).
``superseded_by`` must name another entry. No raw or extracted third-party file is tracked
by git (L3/L4: never redistribute), and no PDF is tracked under docs/ or data/.

``download``: throttled to one request per second, honours robots.txt, records SHA-256 and the
retrieval date in ``manifest.lock.json`` (committed: hashes only), writes raw files to ``raw/`` and
text to ``text/`` (both gitignored). Text-layer PDFs only; a PDF that yields no text is dropped.
"""

import argparse
import hashlib
import subprocess  # nosec B404 - fixed argv only
import sys
import time
from collections.abc import Callable
from datetime import date
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from pypdf import PdfReader

from .common import REPO, dumps_json, read_yaml, write_text

CORPUS = REPO / "data" / "corpus"
BASES = {"L1", "L2", "L3", "L4", "L5", "L6"}
REQUIRED = (
    "doc_id",
    "tag",
    "collection",
    "jurisdiction",
    "legal_basis",
    "format",
    "title",
    "publisher",
    "source_url",
)
USER_AGENT = "CredAssure-capstone-corpus/0.1 (academic research; throttled 1 req/s)"


def audit(manifest: dict[str, Any], tracked: list[str]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Any error fails ``make corpus-audit``."""
    errors: list[str] = []
    warnings: list[str] = []
    docs = manifest.get("documents") or []
    ids = [d.get("doc_id") for d in docs]
    for dup in sorted({i for i in ids if ids.count(i) > 1 and i}):
        errors.append(f"{dup}: duplicate doc_id")
    for d in docs:
        doc_id = d.get("doc_id", "<no doc_id>")
        errors += [f"{doc_id}: missing {key}" for key in REQUIRED if not d.get(key)]
        if "effective_from" not in d:
            errors.append(f"{doc_id}: missing effective_from key")
        elif d["effective_from"] is None:
            warnings.append(f"{doc_id}: effective_from unknown, confirm on the page")
        if d.get("legal_basis") and d["legal_basis"] not in BASES:
            errors.append(f"{doc_id}: legal_basis {d['legal_basis']} is not L1-L6")
        if d.get("source_url") and urlsplit(d["source_url"]).scheme != "https":
            errors.append(f"{doc_id}: source_url is not https")
        if d.get("superseded_by") and d["superseded_by"] not in ids:
            errors.append(f"{doc_id}: superseded_by {d['superseded_by']} is not in the manifest")
    for path in tracked:
        under_corpus = path.startswith(("data/corpus/raw/", "data/corpus/text/"))
        if under_corpus or (path.lower().endswith(".pdf") and path.startswith(("docs/", "data/"))):
            errors.append(
                f"{path}: third-party file tracked by git (L3/L4 must not be redistributed)"
            )
    return errors, warnings


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def extract_text(body: bytes, fmt: str) -> str:
    """Plain text from HTML or a text-layer PDF. Empty string means "drop it"."""
    if fmt == "pdf":
        try:
            reader = PdfReader(BytesIO(body))
            return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception:
            return ""
    parser = _Text()
    parser.feed(body.decode("utf-8", errors="replace"))
    return "\n".join(parser.parts)


def _allowed(client: httpx.Client, url: str, cache: dict[str, RobotFileParser]) -> bool:
    parts = urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    if root not in cache:
        robots = RobotFileParser()
        try:
            response = client.get(f"{root}/robots.txt")
            if response.status_code >= 500:  # RFC 9309: a server error means disallow
                robots.parse(["User-agent: *", "Disallow: /"])
            else:
                robots.parse(response.text.splitlines() if response.status_code == 200 else [])
        except httpx.HTTPError:
            robots.parse([])
        cache[root] = robots
    return cache[root].can_fetch(USER_AGENT, url)


def download(
    docs: list[dict[str, Any]],
    out: Path,
    client: httpx.Client,
    today: date,
    sleep: Callable[[float], None] = time.sleep,
    lock_path: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch every entry once (one request per second). The lock is saved after each document,
    so an interrupted run keeps what it fetched."""
    lock: dict[str, dict[str, Any]] = {}
    robots: dict[str, RobotFileParser] = {}
    for d in docs:
        lock[d["doc_id"]] = _fetch(d, out, client, today, sleep, robots)
        if lock_path is not None:
            write_text(lock_path, dumps_json(lock))
    return lock


def _fetch(
    d: dict[str, Any],
    out: Path,
    client: httpx.Client,
    today: date,
    sleep: Callable[[float], None],
    robots: dict[str, RobotFileParser],
) -> dict[str, Any]:
    doc_id, url = d["doc_id"], d["source_url"]
    record: dict[str, Any] = {"source_url": url, "retrieved_on": today}
    if not _allowed(client, url, robots):
        return {**record, "status": "robots_disallowed"}
    sleep(1.0)
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return {**record, "status": f"error: {type(exc).__name__}"}
    if response.status_code != 200:
        return {**record, "status": f"http_{response.status_code}"}
    body = response.content
    text = extract_text(body, d["format"])
    record |= {
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "final_url": str(response.url),
    }
    if not text:
        return {**record, "status": "dropped_no_text"}
    (out / "raw").mkdir(parents=True, exist_ok=True)
    (out / "raw" / f"{doc_id}.{d['format']}").write_bytes(body)
    write_text(out / "text" / f"{doc_id}.txt", text + "\n")
    return {**record, "status": "ok", "text_sha256": hashlib.sha256(text.encode()).hexdigest()}


def _tracked() -> list[str]:
    result = subprocess.run(  # nosec B603 B607 - fixed argv, git from PATH
        ["git", "ls-files"],  # noqa: S607 - git from PATH, as in every make target
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m credassure.datagen.corpus")
    parser.add_argument("command", choices=["audit", "download"])
    args = parser.parse_args(argv)
    manifest = read_yaml(CORPUS / "manifest.yaml")
    if args.command == "audit":
        errors, warnings = audit(manifest, _tracked())
        for w in warnings:
            print(f"WARN  {w}")
        for e in errors:
            print(f"ERROR {e}", file=sys.stderr)
        docs = manifest["documents"]
        print(f"{len(docs)} documents, {len(errors)} errors, {len(warnings)} warnings")
        return 1 if errors else 0
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        lock = download(
            manifest["documents"],
            CORPUS,
            client,
            date.today(),
            lock_path=CORPUS / "manifest.lock.json",
        )
    ok = sum(1 for x in lock.values() if x["status"] == "ok")
    print(f"{ok}/{len(lock)} documents downloaded and extracted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
