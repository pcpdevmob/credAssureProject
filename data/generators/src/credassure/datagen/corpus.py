"""Real Indian corpus tooling (scope #14, BRD §10, ADR 0019).

- ``audit``: every manifest entry has a canonical doc_id, https URL, legal basis L1-L4,
  jurisdiction ``IN`` or ``IN-XX``, ``applies_to`` and an ``effective_from`` key (null warns).
  ``superseded_by`` names another entry. Real plus synthetic documents stay at or under 2,000. No
  raw or extracted third-party file is tracked by git, and no PDF under docs/ or data/.
- ``Gate``: the only way the scripts touch the network. It honours robots.txt, waits one second
  before every request, never requests a manual-only host, and stops a host for the rest of the
  run on 403, 429, 418, 444, a network or TLS error, or a bot-challenge page. There are no
  retries, no spoofed headers and no headless browser.
- ``download``: fetches entries still ``pending``. ``import_raw`` ingests files an owner saved
  to ``raw/`` by hand (``ok_manual``). ``verify`` checks local raw files against the lock hashes.
  A PDF without a text layer is ``rejected_no_text`` and never counts. Raw and text folders are
  gitignored; the lock (hashes, status, legal basis) is committed.
"""

import hashlib
import re
import subprocess  # nosec B404 - fixed argv only
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

from .common import REPO, write_text

CORPUS = REPO / "data" / "corpus"
BASES = {"L1", "L2", "L3", "L4"}  # real documents only; L5 is synthetic, L6 was removed (ADR 0019)
APPLIES_TO = {"commercial_bank", "nbfc", "sfb", "coop_bank", "all"}
JURISDICTION = re.compile(r"^IN(?:-[A-Z]{2})?$")
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
    "applies_to",
    "source",
    "method",
)
OK = {"ok", "ok_manual"}
PENDING = "PENDING"
MAX_DOCUMENTS = 2_000
USER_AGENT = "CredAssure-capstone-corpus/0.1 (academic research; throttled 1 req/s)"
BLOCK_STATUS = {403, 418, 429, 444}
CHALLENGE = ("captcha", "cf-chl", "access denied", "request unsuccessful", "are you a robot")
MIN_PDF_TEXT = 200  # fewer characters means a scan with page numbers only, not a text layer
EXTENSIONS = {".pdf": "pdf", ".html": "html", ".htm": "html"}


def audit(
    manifest: dict[str, Any], tracked: list[str], synthetic: int = 0
) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Any error fails ``make corpus-audit``."""
    errors: list[str] = []
    warnings: list[str] = []
    docs = manifest.get("documents") or []
    ids = [d.get("doc_id") for d in docs]
    for dup in sorted({i for i in ids if ids.count(i) > 1 and i}):
        errors.append(f"{dup}: duplicate doc_id")
    if len(docs) + synthetic > MAX_DOCUMENTS:
        errors.append(f"{len(docs)} real + {synthetic} synthetic documents exceed {MAX_DOCUMENTS}")
    for d in docs:
        doc_id = d.get("doc_id", "<no doc_id>")
        errors += [f"{doc_id}: missing {key}" for key in REQUIRED if not d.get(key)]
        if "effective_from" not in d:
            errors.append(f"{doc_id}: missing effective_from key")
        elif d["effective_from"] is None:
            warnings.append(f"{doc_id}: effective_from unknown, confirm on the page")
        if d.get("legal_basis") and d["legal_basis"] not in BASES:
            errors.append(f"{doc_id}: legal_basis {d['legal_basis']} is not L1-L4")
        if d.get("jurisdiction") and not JURISDICTION.match(str(d["jurisdiction"])):
            errors.append(f"{doc_id}: jurisdiction {d['jurisdiction']} is not IN or IN-XX")
        if d.get("applies_to") and d["applies_to"] not in APPLIES_TO:
            errors.append(
                f"{doc_id}: applies_to {d['applies_to']} is not one of {sorted(APPLIES_TO)}"
            )
        if d.get("source_url") and urlsplit(d["source_url"]).scheme != "https":
            errors.append(f"{doc_id}: source_url is not https")
        if d.get("superseded_by") and d["superseded_by"] not in ids:
            errors.append(f"{doc_id}: superseded_by {d['superseded_by']} is not in the manifest")
        if d.get("title") == PENDING:
            warnings.append(f"{doc_id}: manual slot not filled yet")
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
    """Plain text from HTML or a text-layer PDF. Empty string means "reject it"."""
    if fmt == "pdf":
        try:
            reader = PdfReader(BytesIO(body))
            text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
            return text if len(text) >= MIN_PDF_TEXT else ""
        except Exception:
            return ""
    parser = _Text()
    parser.feed(body.decode("utf-8", errors="replace"))
    return "\n".join(parser.parts)


class Gate:
    """Polite access to one run's hosts. Returns a response, or a reason string when it refuses."""

    def __init__(
        self, client: httpx.Client, manual_hosts: set[str], sleep: Callable[[float], None]
    ) -> None:
        self.client = client
        self.manual_hosts = manual_hosts
        self.sleep = sleep
        self.robots: dict[str, RobotFileParser] = {}
        self.blocked: dict[str, str] = {}

    def _robots(self, url: str) -> RobotFileParser | str:
        parts = urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        if root not in self.robots:
            robots = RobotFileParser()
            self.sleep(1.0)
            try:
                response = self.client.get(f"{root}/robots.txt")
            except httpx.HTTPError as exc:
                return f"error: {type(exc).__name__}"
            if response.status_code in BLOCK_STATUS or response.status_code >= 500:
                robots.parse(
                    ["User-agent: *", "Disallow: /"]
                )  # RFC 9309: unreachable means disallow
            else:
                robots.parse(response.text.splitlines() if response.status_code == 200 else [])
            self.robots[root] = robots
        return self.robots[root]

    def get(self, url: str, form: dict[str, str] | None = None) -> httpx.Response | str:
        """GET ``url``, or submit the page's own HTML form fields (``form``) by POST."""
        host = urlsplit(url).hostname or ""
        if host in self.manual_hosts:
            return "manual_host"
        if host in self.blocked:
            return f"host_blocked: {self.blocked[host]}"
        robots = self._robots(url)
        if isinstance(robots, str):
            self.blocked[host] = robots
            return f"host_blocked: {robots}"
        if not robots.can_fetch(USER_AGENT, url):
            return "robots_disallowed"
        self.sleep(1.0)
        try:
            response = self.client.post(url, data=form) if form else self.client.get(url)
        except httpx.HTTPError as exc:  # connection, TLS or timeout: stop the host, never retry
            self.blocked[host] = f"error: {type(exc).__name__}"
            return f"host_blocked: {self.blocked[host]}"
        if response.status_code in BLOCK_STATUS:
            self.blocked[host] = f"http_{response.status_code}"
            return f"host_blocked: {self.blocked[host]}"
        if "html" in response.headers.get("content-type", "text/html"):
            head = response.text[:4096].lower()
            if any(marker in head for marker in CHALLENGE):
                self.blocked[host] = "bot_challenge"
                return "host_blocked: bot_challenge"
        return response


def _store(
    doc_id: str, body: bytes, fmt: str, out: Path, record: dict[str, Any], status: str
) -> dict[str, Any]:
    record = {
        **record,
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        "raw_file": f"{doc_id}.{fmt}",
    }
    text = extract_text(body, fmt)
    if not text:
        return {**record, "status": "rejected_no_text"}
    (out / "raw").mkdir(parents=True, exist_ok=True)
    raw = out / "raw" / record["raw_file"]
    if not raw.exists() or raw.read_bytes() != body:
        raw.write_bytes(body)
    write_text(out / "text" / f"{doc_id}.txt", text + "\n")
    return {**record, "status": status, "text_sha256": hashlib.sha256(text.encode()).hexdigest()}


def download(
    docs: list[dict[str, Any]],
    lock: dict[str, dict[str, Any]],
    out: Path,
    gate: Gate,
    today: date,
    save: Callable[[], None] = lambda: None,
) -> None:
    """Fetch every script entry still ``pending``. Updates ``lock`` in place, saving after each."""
    for d in docs:
        doc_id = d["doc_id"]
        current = lock.get(doc_id, {})
        if current.get("status") not in (None, "pending"):
            continue
        base = {
            "source_url": d["source_url"],
            "legal_basis": d["legal_basis"],
            "retrieved_on": today,
        }
        if d["method"] == "manual" or d["title"] == PENDING:
            lock[doc_id] = {**base, "status": "pending_manual", "reason": "manual source"}
            continue
        response = gate.get(d["source_url"])
        if isinstance(response, str):
            status = "pending_manual" if response != "robots_disallowed" else "robots_disallowed"
            lock[doc_id] = {**base, "status": status, "reason": response}
        elif response.status_code != 200:
            lock[doc_id] = {
                **base,
                "status": f"http_{response.status_code}",
                "reason": "fix the URL or download by hand",
            }
        else:
            record = {**base, "final_url": str(response.url)}
            lock[doc_id] = _store(doc_id, response.content, d["format"], out, record, "ok")
        save()


def import_raw(
    docs: list[dict[str, Any]], lock: dict[str, dict[str, Any]], out: Path, today: date
) -> list[str]:
    """Ingest files saved by hand as ``raw/<doc_id>.<pdf|html|htm>``. Returns errors."""
    by_id = {d["doc_id"]: d for d in docs}
    errors: list[str] = []
    for path in sorted(p for p in (out / "raw").glob("*") if p.is_file()):
        fmt = EXTENSIONS.get(path.suffix.lower())
        doc = by_id.get(path.stem)
        if fmt is None:
            errors.append(f"{path.name}: only .pdf, .html or .htm are accepted")
            continue
        if doc is None:
            errors.append(
                f"{path.name}: no manifest entry {path.stem}; rename the file to its doc_id"
            )
            continue
        if doc["title"] == PENDING:
            errors.append(
                f"{path.name}: fill title, source_url and dates for {path.stem} "
                "in manifest.yaml first"
            )
            continue
        body = path.read_bytes()
        current = lock.get(path.stem, {})
        if (
            current.get("status") in OK
            and current.get("sha256") == hashlib.sha256(body).hexdigest()
        ):
            continue
        record = {
            "source_url": doc["source_url"],
            "legal_basis": doc["legal_basis"],
            "retrieved_on": today,
        }
        lock[path.stem] = _store(path.stem, body, fmt, out, record, "ok_manual")
        if lock[path.stem]["status"] == "rejected_no_text":
            (out / "raw" / "rejected").mkdir(
                exist_ok=True
            )  # keep the owner's file; OCR is out of scope
            path.rename(out / "raw" / "rejected" / path.name)
    return errors


def verify(lock: dict[str, dict[str, Any]], raw: Path) -> tuple[list[str], list[str], list[str]]:
    """(identical, missing, mismatched) doc_ids for every lock entry that has a raw file hash."""
    identical, missing, mismatched = [], [], []
    for doc_id, record in sorted(lock.items()):
        if record.get("status") not in OK or "raw_file" not in record:
            continue
        path = raw / record["raw_file"]
        if not path.exists():
            missing.append(doc_id)
        elif hashlib.sha256(path.read_bytes()).hexdigest() == record["sha256"]:
            identical.append(doc_id)
        else:
            mismatched.append(doc_id)
    return identical, missing, mismatched


def tracked_files() -> list[str]:
    result = subprocess.run(  # nosec B603 B607 - fixed argv, git from PATH
        ["git", "ls-files"],  # noqa: S607 - git from PATH, as in every make target
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.splitlines()
