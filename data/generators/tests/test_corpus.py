"""Scope #14 / ADR 0019: corpus audit, polite gate, download, import and verify (no network)."""

import hashlib
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from credassure.datagen.common import REPO, read_yaml
from credassure.datagen.corpus import (
    SYNTHETIC_PDF_DIRS,
    Gate,
    audit,
    download,
    extract_text,
    import_raw,
    tracked_files,
    verify,
)

TODAY = date(2026, 11, 5)


def _gate(handler: Any, sleeps: list[float] | None = None, manual: set[str] | None = None) -> Gate:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return Gate(client, manual or set(), (sleeps if sleeps is not None else []).append)


def test_KR04_committed_manifest_passes_the_audit() -> None:
    import json

    manifest = read_yaml(REPO / "data" / "corpus" / "manifest.yaml")
    lock = json.loads((REPO / "data" / "corpus" / "manifest.lock.json").read_text(encoding="utf-8"))
    errors, _ = audit(manifest, [], lock=lock)
    assert errors == []
    assert all(d["jurisdiction"].startswith("IN") for d in manifest["documents"])


def test_KR04_audit_rejects_bad_entries(entry: Callable[..., dict[str, Any]]) -> None:
    bad = [
        entry(doc_id="A", legal_basis=None),
        entry(doc_id="B", legal_basis="L6"),
        entry(doc_id="B2", legal_basis="L5"),
        entry(doc_id="C", superseded_by="NOPE"),
        entry(doc_id="D", source_url="http://insecure.example"),
        entry(doc_id="D"),
        {k: v for k, v in entry(doc_id="E").items() if k != "effective_from"},
        entry(doc_id="F", jurisdiction="US"),
        entry(doc_id="G", applies_to="hfc"),
    ]
    errors, _ = audit({"documents": bad}, [])
    joined = "\n".join(errors)
    for needle in (
        "A: missing legal_basis",
        "B: legal_basis L6",
        "B2: legal_basis L5",
        "C: superseded_by NOPE",
        "D: source_url is not https",
        "D: duplicate doc_id",
        "E: missing effective_from",
        "F: jurisdiction US",
        "G: applies_to hfc",
    ):
        assert needle in joined


def test_KR04_state_codes_pass_and_the_2000_cap_holds(entry: Callable[..., dict[str, Any]]) -> None:
    errors, _ = audit({"documents": [entry(jurisdiction="IN-MH")]}, [])
    assert errors == []
    errors, _ = audit({"documents": [entry()]}, [], synthetic=2_000)
    assert any("exceed 2000" in e for e in errors)


def test_scope14_audit_fails_on_tracked_third_party_files(
    entry: Callable[..., dict[str, Any]],
) -> None:
    errors, _ = audit(
        {"documents": [entry()]},
        ["data/corpus/raw/R-X-001.pdf", "docs/source/170MD.pdf", "README.md"],
    )
    assert len(errors) == 2


def test_scope14_only_the_synthetic_test_pack_may_track_pdfs(
    entry: Callable[..., dict[str, Any]],
) -> None:
    errors, _ = audit(
        {"documents": [entry()]},
        [
            "data/test-pack/01-director-route/lender-pdfs/a.pdf",
            "data/test-packs/x.pdf",
            "data/x.pdf",
        ],
    )
    assert len(errors) == 2  # only the exact synthetic folder is allowed


def test_scope14_every_tracked_test_pack_pdf_says_it_is_synthetic() -> None:
    from pypdf import PdfReader

    pdfs = [
        REPO / p for p in tracked_files() if p.startswith(SYNTHETIC_PDF_DIRS) and p.endswith(".pdf")
    ]
    assert pdfs  # the pack is tracked
    for p in pdfs:
        text = " ".join(page.extract_text() or "" for page in PdfReader(p).pages).lower()
        assert "synthetic" in text, p


def test_scope14_repo_tracks_no_third_party_file() -> None:
    errors, _ = audit({"documents": []}, tracked_files())
    assert errors == []


def test_scope14_extract_text_drops_scripts_and_unreadable_pdfs(
    text_pdf: Callable[[str], bytes],
) -> None:
    html = b"<html><script>x=1</script><h1>KFS</h1><p>APR 12%</p></html>"
    assert extract_text(html, "html") == "KFS\nAPR 12%"
    assert extract_text(b"not a pdf", "pdf") == ""
    long = "CGTMSE circular " * 20
    assert extract_text(text_pdf(long), "pdf").startswith("CGTMSE circular")
    assert extract_text(text_pdf("Page 1"), "pdf") == ""  # page numbers only: a scan


def test_ADR0019_gate_throttles_honours_robots_and_skips_manual_hosts() -> None:
    hits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /private\n")
        return httpx.Response(200, text="<p>ok</p>")

    sleeps: list[float] = []
    gate = _gate(handler, sleeps, manual={"rbi.org.in"})
    assert isinstance(gate.get("https://ex.org/a"), httpx.Response)
    assert gate.get("https://ex.org/private/b") == "robots_disallowed"
    assert gate.get("https://rbi.org.in/x") == "manual_host"
    assert sleeps == [1.0, 1.0]  # robots.txt once, then the one allowed page
    assert not any("rbi.org.in" in h for h in hits)


def test_ADR0019_gate_stops_a_host_on_block_or_challenge_without_retry() -> None:
    hits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(request.url.host + request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        if request.url.host == "blocked.in":
            return httpx.Response(429)
        return httpx.Response(
            200,
            text="<title>Please complete the CAPTCHA</title>",
            headers={"content-type": "text/html"},
        )

    gate = _gate(handler)
    assert gate.get("https://blocked.in/a") == "host_blocked: http_429"
    assert gate.get("https://blocked.in/b") == "host_blocked: http_429"
    assert gate.get("https://challenge.in/a") == "host_blocked: bot_challenge"
    assert gate.get("https://challenge.in/b") == "host_blocked: bot_challenge"
    assert hits.count("blocked.in/b") == 0 and hits.count("challenge.in/b") == 0


def test_ADR0019_robots_server_error_means_disallow() -> None:
    gate = _gate(lambda r: httpx.Response(503 if r.url.path == "/robots.txt" else 200, text="x"))
    assert gate.get("https://ex.org/a") == "robots_disallowed"


def test_scope14_download_stores_hashes_and_routes_failures(
    tmp_path: Path, entry: Callable[..., dict[str, Any]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        if request.url.path == "/missing":
            return httpx.Response(404)
        if request.url.path == "/scan.pdf":
            return httpx.Response(
                200, content=b"%PDF-1.4 no text layer", headers={"content-type": "application/pdf"}
            )
        return httpx.Response(200, text="<p>Directions text</p>")

    docs = [
        entry(doc_id="OK", source_url="https://ex.org/doc"),
        entry(doc_id="GONE", source_url="https://ex.org/missing"),
        entry(doc_id="SCAN", format="pdf", source_url="https://ex.org/scan.pdf"),
        entry(doc_id="SLOT", title="PENDING", method="manual"),
        entry(doc_id="DONE"),
    ]
    lock: dict[str, dict[str, Any]] = {"DONE": {"status": "ok"}}
    saves: list[int] = []
    download(docs, lock, tmp_path, _gate(handler), TODAY, lambda: saves.append(1))
    assert {k: v["status"] for k, v in lock.items()} == {
        "OK": "ok",
        "GONE": "http_404",
        "SCAN": "rejected_no_text",
        "SLOT": "pending_manual",
        "DONE": "ok",
    }
    assert lock["OK"]["sha256"] == hashlib.sha256(b"<p>Directions text</p>").hexdigest()
    assert lock["OK"]["legal_basis"] == "L4"
    assert (tmp_path / "text" / "OK.txt").read_text(encoding="utf-8") == "Directions text\n"
    assert not (tmp_path / "raw" / "SCAN.pdf").exists()
    assert len(saves) == 3  # saved after every fetched document


def test_scope14_import_accepts_text_rejects_scans_and_unknown_names(
    tmp_path: Path, entry: Callable[..., dict[str, Any]], text_pdf: Callable[[str], bytes]
) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "R-X-001.pdf").write_bytes(text_pdf("Master Direction " * 20))
    (raw / "R-X-002.pdf").write_bytes(b"%PDF-1.4 scanned image only")
    (raw / "R-X-003.html").write_text("<p>slot</p>", encoding="utf-8")
    (raw / "stray.pdf").write_bytes(b"x")
    (raw / "notes.docx").write_bytes(b"x")
    docs = [
        entry(doc_id="R-X-001", format="pdf"),
        entry(doc_id="R-X-002", format="pdf"),
        entry(doc_id="R-X-003", title="PENDING"),
    ]
    lock: dict[str, dict[str, Any]] = {}
    errors = import_raw(docs, lock, tmp_path, TODAY)
    assert lock["R-X-001"]["status"] == "ok_manual"
    assert lock["R-X-002"]["status"] == "rejected_no_text"
    assert "R-X-003" not in lock
    assert len(errors) == 3  # PENDING slot, unknown doc_id, wrong extension
    assert (tmp_path / "text" / "R-X-001.txt").exists()
    assert not (raw / "R-X-002.pdf").exists()
    assert (tmp_path / "quarantine" / "R-X-002.pdf").exists()
    assert import_raw(docs, lock, tmp_path, TODAY) == errors  # idempotent


def test_scope14_verify_reports_identical_missing_and_mismatched(tmp_path: Path) -> None:
    (tmp_path / "A.pdf").write_bytes(b"a")
    (tmp_path / "C.pdf").write_bytes(b"tampered")
    digest = hashlib.sha256(b"a").hexdigest()
    lock = {
        "A": {"status": "ok", "raw_file": "A.pdf", "sha256": digest},
        "B": {"status": "ok_manual", "raw_file": "B.pdf", "sha256": digest},
        "C": {"status": "ok", "raw_file": "C.pdf", "sha256": digest},
        "D": {"status": "pending_manual"},
    }
    assert verify(lock, tmp_path) == (["A"], ["B"], ["C"])


def test_KR04_available_document_without_a_date_is_an_audit_error(
    entry: Callable[..., dict[str, Any]],
) -> None:
    docs = [entry(doc_id="A", effective_from=None), entry(doc_id="B", effective_from=None)]
    lock = {"A": {"status": "ok"}, "B": {"status": "pending_manual"}}
    errors, warnings = audit({"documents": docs}, [], lock=lock)
    assert errors == ["A: available but effective_from is missing (make corpus-dates)"]
    assert any(w.startswith("B:") for w in warnings)


def test_scope14_import_refuses_duplicates_but_not_large_files(
    tmp_path: Path, entry: Callable[..., dict[str, Any]], text_pdf: Callable[[str], bytes]
) -> None:
    import credassure.datagen.corpus as corpus

    raw = tmp_path / "raw"
    raw.mkdir()
    body = text_pdf("Master Direction " * 20)
    (raw / "R-X-002.pdf").write_bytes(body)
    (raw / "R-X-003.pdf").write_bytes(text_pdf("Lending policy " * 400))
    lock = {"R-X-001": {"status": "ok", "sha256": hashlib.sha256(body).hexdigest()}}
    docs = [entry(doc_id=i, format="pdf") for i in ("R-X-001", "R-X-002", "R-X-003")]
    limit = corpus.MAX_SCRIPT_BYTES
    corpus.MAX_SCRIPT_BYTES = 32  # smaller than both files: the script cap never limits imports
    try:
        errors = import_raw(docs, lock, tmp_path, TODAY)
    finally:
        corpus.MAX_SCRIPT_BYTES = limit
    assert any("duplicate of R-X-001" in e for e in errors)
    assert "R-X-002" not in lock
    assert lock["R-X-003"]["status"] == "ok_manual" and not any("R-X-003" in e for e in errors)


def test_KR04_available_document_needs_a_date_source(entry: Callable[..., dict[str, Any]]) -> None:
    errors, _ = audit({"documents": [entry(doc_id="A")]}, [], lock={"A": {"status": "ok"}})
    assert errors == ["A: available but date_source is missing (make corpus-dates)"]
