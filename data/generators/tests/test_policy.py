"""ADR 0020 controls: contactable User-Agent, host terms, size cap, quarantine, page cap."""

from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from credassure.datagen import corpus
from credassure.datagen.common import user_agent
from credassure.datagen.corpus import Gate, audit, download
from credassure.datagen.harvest import ensure_hosts, hosts_missing_terms, restricted_hosts

TODAY = date(2026, 11, 5)


def test_ADR0020_user_agent_contact_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    base = "CredAssure-capstone/1.0 (IIT KGP academic project"
    monkeypatch.delenv("CORPUS_CONTACT_EMAIL", raising=False)
    monkeypatch.delenv("CORPUS_CONTACT_URL", raising=False)
    assert user_agent() == f"{base})"
    monkeypatch.setenv("CORPUS_CONTACT_URL", "https://github.com/example/credassure")
    assert user_agent() == f"{base}; +https://github.com/example/credassure)"
    monkeypatch.setenv("CORPUS_CONTACT_EMAIL", "team@example.org")
    assert user_agent() == f"{base}; contact: team@example.org)"  # email wins over URL


@pytest.mark.parametrize(
    ("name", "value"),
    [("CORPUS_CONTACT_EMAIL", "not-an-email"), ("CORPUS_CONTACT_URL", "ftp://x")],
)
def test_ADR0020_malformed_contact_stops_the_run(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str
) -> None:
    monkeypatch.delenv("CORPUS_CONTACT_EMAIL", raising=False)
    monkeypatch.setenv(name, value)
    with pytest.raises(SystemExit, match=name):
        user_agent()


def test_ADR0020_restricted_host_is_never_requested_and_goes_manual(
    tmp_path: Path, entry: Callable[..., dict[str, Any]]
) -> None:
    hits: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hits.append(str(request.url))
        return httpx.Response(200, text="<p>x</p>")

    manifest = {
        "documents": [entry(doc_id="A", source_url="https://closed.gov.in/a")],
        "hosts": {
            "closed.gov.in": {
                "terms_url": "https://closed.gov.in/terms",
                "terms_note": "no automated access",
                "automated_access": "restricted",
            }
        },
    }
    gate = Gate(
        httpx.Client(transport=httpx.MockTransport(handler)),
        set(),
        lambda _: None,
        restricted_hosts(manifest),
    )
    lock: dict[str, dict[str, Any]] = {}
    download(manifest["documents"], lock, tmp_path, gate, TODAY)
    assert hits == []
    assert lock["A"]["status"] == "pending_manual"
    assert lock["A"]["reason"] == "terms restrict automated access"


def test_ADR0020_new_hosts_are_unknown_and_listed_for_owners(
    entry: Callable[..., dict[str, Any]],
) -> None:
    manifest: dict[str, Any] = {
        "documents": [
            entry(doc_id="A", source_url="https://sidbi.in/x"),
            entry(doc_id="B", source_url="https://www.cgtmse.in/y"),
        ]
    }
    assert ensure_hosts(manifest) == 2
    manifest["hosts"]["sidbi.in"] |= {
        "terms_url": "https://sidbi.in/terms",
        "terms_note": "ok",
        "automated_access": "allowed",
    }
    assert ensure_hosts(manifest) == 0  # never overwrites a person's entry
    rows = hosts_missing_terms(manifest, {"B": {"owner": "[Name 3]"}})
    assert any("www.cgtmse.in | 1 | [Name 3] | unknown" in r for r in rows)
    assert not any("sidbi.in |" in r for r in rows)


def test_ADR0020_audit_rejects_invalid_access_value(entry: Callable[..., dict[str, Any]]) -> None:
    manifest = {"documents": [entry()], "hosts": {"ex.org": {"automated_access": "maybe"}}}
    errors, _ = audit(manifest, [])
    assert errors == ["host ex.org: automated_access must be allowed, restricted or unknown"]


def test_ADR0020_oversize_download_is_refused_and_not_stored(
    tmp_path: Path, entry: Callable[..., dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(corpus, "MAX_SCRIPT_BYTES", 100)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        return httpx.Response(
            200, content=b"x" * 500
        )  # no Content-Length trust needed: streamed cap

    gate = Gate(httpx.Client(transport=httpx.MockTransport(handler)), set(), lambda _: None)
    lock: dict[str, dict[str, Any]] = {}
    download([entry(doc_id="BIG")], lock, tmp_path, gate, TODAY)
    assert lock["BIG"]["status"] == "rejected_too_large"
    assert not (tmp_path / "raw").exists()


def test_ADR0020_no_text_download_is_quarantined(
    tmp_path: Path, entry: Callable[..., dict[str, Any]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        return httpx.Response(
            200, content=b"%PDF-1.4 scan", headers={"content-type": "application/pdf"}
        )

    gate = Gate(httpx.Client(transport=httpx.MockTransport(handler)), set(), lambda _: None)
    lock: dict[str, dict[str, Any]] = {}
    download([entry(doc_id="SCAN", format="pdf")], lock, tmp_path, gate, TODAY)
    assert lock["SCAN"]["status"] == "rejected_no_text"
    assert (tmp_path / "quarantine" / "SCAN.pdf").exists()
    assert not (tmp_path / "raw" / "SCAN.pdf").exists()


def test_ADR0020_extraction_reads_at_most_max_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(5):
        writer.add_blank_page(100, 100)
    buf = io.BytesIO()
    writer.write(buf)
    seen: list[int] = []

    class Page:
        def __init__(self, n: int) -> None:
            self.n = n

        def extract_text(self) -> str:
            seen.append(self.n)
            return "x" * 300

    class Reader:
        def __init__(self, _: Any) -> None:
            self.pages = [Page(i) for i in range(5)]

    monkeypatch.setattr(corpus, "MAX_PAGES", 2)
    monkeypatch.setattr(corpus, "PdfReader", Reader)
    assert corpus.extract_text(buf.getvalue(), "pdf")
    assert seen == [0, 1]
