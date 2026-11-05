"""Scope #14: corpus legal-basis audit and the throttled downloader (no network)."""

from datetime import date
from pathlib import Path
from typing import Any

import httpx

from credassure.datagen.common import REPO, read_yaml
from credassure.datagen.corpus import _tracked, audit, download, extract_text

GOOD: dict[str, Any] = {
    "doc_id": "R-X-01",
    "tag": "rbi_md",
    "collection": "public",
    "jurisdiction": "IN",
    "legal_basis": "L4",
    "format": "html",
    "title": "t",
    "publisher": "p",
    "effective_from": "2025-01-01",
    "superseded_by": None,
    "source_url": "https://example.org/a",
}


def test_scope14_committed_manifest_passes_the_audit() -> None:
    manifest = read_yaml(REPO / "data" / "corpus" / "manifest.yaml")
    errors, _ = audit(manifest, [])
    assert errors == []
    assert len(manifest["documents"]) >= 60


def test_scope14_audit_fails_on_bad_entries() -> None:
    bad = [
        {**GOOD, "doc_id": "A", "legal_basis": None},
        {**GOOD, "doc_id": "B", "legal_basis": "L9"},
        {**GOOD, "doc_id": "C", "superseded_by": "NOPE"},
        {**GOOD, "doc_id": "D", "source_url": "http://insecure.example"},
        {**GOOD, "doc_id": "D"},
        {k: v for k, v in GOOD.items() if k != "effective_from"} | {"doc_id": "E"},
    ]
    errors, _ = audit({"documents": bad}, [])
    joined = "\n".join(errors)
    needles = (
        "A: missing legal_basis",
        "B: legal_basis L9",
        "C: superseded_by NOPE",
        "D: source_url is not https",
        "D: duplicate doc_id",
        "E: missing effective_from",
    )
    for needle in needles:
        assert needle in joined


def test_scope14_audit_fails_on_tracked_third_party_files() -> None:
    errors, _ = audit(
        {"documents": [GOOD]}, ["data/corpus/raw/R-X-01.pdf", "docs/source/170MD.pdf", "README.md"]
    )
    assert len(errors) == 2


def test_scope14_repo_tracks_no_third_party_pdf() -> None:
    errors, _ = audit({"documents": []}, _tracked())
    assert errors == []


def test_scope14_extract_text_drops_scripts_and_unreadable_pdfs() -> None:
    html = b"<html><script>x=1</script><h1>KFS</h1><p>APR 12%</p></html>"
    assert extract_text(html, "html") == "KFS\nAPR 12%"
    assert extract_text(b"not a pdf", "pdf") == ""


def test_scope14_download_throttles_honours_robots_and_hashes(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        if request.url.path == "/missing":
            return httpx.Response(404)
        if request.url.path == "/scan.pdf":
            return httpx.Response(200, content=b"%PDF-1.4 no text layer")
        return httpx.Response(200, content=b"<p>Directions text</p>")

    docs = [
        {**GOOD, "doc_id": "OK", "source_url": "https://ex.org/doc"},
        {**GOOD, "doc_id": "NO", "source_url": "https://ex.org/private/doc"},
        {**GOOD, "doc_id": "GONE", "source_url": "https://ex.org/missing"},
        {**GOOD, "doc_id": "SCAN", "format": "pdf", "source_url": "https://ex.org/scan.pdf"},
    ]
    sleeps: list[float] = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        lock = download(
            docs,
            tmp_path,
            client,
            date(2026, 11, 5),
            sleep=sleeps.append,
            lock_path=tmp_path / "lock.json",
        )
    assert {k: v["status"] for k, v in lock.items()} == {
        "OK": "ok",
        "NO": "robots_disallowed",
        "GONE": "http_404",
        "SCAN": "dropped_no_text",
    }
    assert sleeps == [1.0, 1.0, 1.0]  # one pause before every real request
    assert len(lock["OK"]["sha256"]) == 64
    assert (tmp_path / "text" / "OK.txt").read_text(encoding="utf-8") == "Directions text\n"
    assert not (tmp_path / "raw" / "SCAN.pdf").exists()
    assert (tmp_path / "lock.json").exists()


def test_scope14_robots_server_error_means_disallow(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503 if request.url.path == "/robots.txt" else 200, text="x")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        lock = download([GOOD], tmp_path, client, date(2026, 11, 5), sleep=lambda _: None)
    assert lock["R-X-01"]["status"] == "robots_disallowed"
