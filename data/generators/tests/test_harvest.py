"""ADR 0019: harvest index pages, top up manual slots, owner sections, report (no network)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from credassure.datagen.corpus import Gate
from credassure.datagen.harvest import (
    assign,
    ensure_slots,
    harvest,
    links,
    manual_markdown,
    report,
)

INDEX = """
<a href="/Default/ViewFile/?id=2_Circular%20262.pdf&amp;path=Circular">Circular 262
dated 12.10.2026</a>
<a href="/Default/ViewFile/?id=1_Circular%20261.pdf&amp;path=Circular">Circular 261</a>
<a href="javascript:void(0)">Next</a>
<a href="https://other.example/x.pdf">offsite</a>
<a href="/Home/About">About</a>
"""
PATTERN = r'/Default/ViewFile/\?id=\d+_[^"&]+&(?:amp;)?path=Circular'


def _sources(**over: Any) -> dict[str, Any]:
    src = {
        "id": 4,
        "name": "CGTMSE",
        "prefix": "R-CG-C",
        "target": 3,
        "basis": "L4",
        "applies_to": "all",
        "jurisdiction": ["IN"],
        "agents": ["LendWise"],
        "method": "script",
        "index_urls": ["https://www.cgtmse.in/Circulars"],
        "link_pattern": PATTERN,
    } | over
    return {"manual_hosts": ["rbi.org.in"], "sources": [src]}


def _gate(handler: Any) -> Gate:
    return Gate(
        httpx.Client(transport=httpx.MockTransport(handler)), {"rbi.org.in"}, lambda _: None
    )


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text="" if request.url.path == "/robots.txt" else INDEX)


def test_KR01_links_are_same_host_sorted_and_pattern_matched() -> None:
    found = links(INDEX, "https://www.cgtmse.in/Circulars", PATTERN)
    assert [u for u, _ in found] == [
        "https://www.cgtmse.in/Default/ViewFile/?id=1_Circular%20261.pdf&path=Circular",
        "https://www.cgtmse.in/Default/ViewFile/?id=2_Circular%20262.pdf&path=Circular",
    ]


def test_KR01_harvest_appends_with_dates_and_respects_the_target(
    entry: Callable[..., dict[str, Any]],
) -> None:
    manifest: dict[str, Any] = {"documents": [entry(doc_id="R-CG-01", source=4)]}
    lock: dict[str, dict[str, Any]] = {}
    added = harvest(_sources(), manifest, lock, _gate(_ok))
    assert added == 2
    new = manifest["documents"][1:]
    assert [d["doc_id"] for d in new] == ["R-CG-C-001", "R-CG-C-002"]
    assert new[1]["effective_from"] == "2026-10-12"
    assert all(lock[d["doc_id"]]["status"] == "pending" for d in new)
    assert harvest(_sources(), manifest, lock, _gate(_ok)) == 0  # append-only, no duplicates


def test_ADR0019_blocked_index_adds_nothing_and_slots_fill_the_target() -> None:
    def blocked(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200 if request.url.path == "/robots.txt" else 403, text="")

    manifest: dict[str, Any] = {"documents": []}
    lock: dict[str, dict[str, Any]] = {}
    assert harvest(_sources(), manifest, lock, _gate(blocked)) == 0
    assert ensure_slots(_sources(), manifest, lock) == 3
    assert {d["title"] for d in manifest["documents"]} == {"PENDING"}
    assert {v["status"] for v in lock.values()} == {"pending_manual"}


def test_ADR0019_rejected_no_text_gets_a_replacement_slot(
    entry: Callable[..., dict[str, Any]],
) -> None:
    manifest = {"documents": [entry(doc_id="R-CG-C-001", source=4)]}
    lock: dict[str, dict[str, Any]] = {"R-CG-C-001": {"status": "rejected_no_text"}}
    assert ensure_slots(_sources(target=1), manifest, lock) == 1
    assert "R-CG-C-002" in lock


def test_ADR0019_state_slots_cycle_through_jurisdictions() -> None:
    sources = _sources(
        id=16,
        prefix="R-STATE",
        target=4,
        method="manual",
        jurisdiction=["IN-MH", "IN-MH", "IN-GJ", "IN-KA"],
    )
    manifest: dict[str, Any] = {"documents": []}
    ensure_slots(sources, manifest, {})
    assert [d["jurisdiction"] for d in manifest["documents"]] == [
        "IN-MH",
        "IN-MH",
        "IN-GJ",
        "IN-KA",
    ]


def test_ADR0019_six_owner_sections_are_balanced_and_keep_small_hosts_whole(
    entry: Callable[..., dict[str, Any]],
) -> None:
    items = (
        [entry(doc_id=f"R{i}", source_url="https://rbi.org.in/x") for i in range(60)]
        + [entry(doc_id=f"C{i}", source_url="https://cgtmse.in/x") for i in range(12)]
        + [entry(doc_id=f"S{i}", source_url="https://sci.gov.in/x") for i in range(6)]
    )
    sections = assign(items)
    sizes = sorted(len(s) for s in sections)
    assert len(sections) == 6 and sum(sizes) == 78 and sizes[-1] - sizes[0] <= 13
    owners_of_sci = [
        i for i, s in enumerate(sections) if any(d["doc_id"].startswith("S") for d in s)
    ]
    assert len(owners_of_sci) == 1


def test_ADR0019_manual_markdown_lists_pending_not_available(
    entry: Callable[..., dict[str, Any]],
) -> None:
    manifest = {
        "documents": [entry(doc_id="A"), entry(doc_id="B", title="PENDING"), entry(doc_id="C")]
    }
    lock = {
        "A": {"status": "ok"},
        "B": {"status": "pending_manual", "reason": "manual source"},
        "C": {"status": "rejected_no_text"},
    }
    text = manual_markdown(manifest, lock)
    assert "| B |" in text and "| A |" not in text
    assert "## [Name 6]" in text and "Rejected" in text


def test_G2_report_counts_only_ok_with_extracted_text(
    tmp_path: Path, entry: Callable[..., dict[str, Any]]
) -> None:
    (tmp_path / "A.txt").write_text("x", encoding="utf-8")
    manifest = {
        "documents": [entry(doc_id="A"), entry(doc_id="B"), entry(doc_id="C"), entry(doc_id="D")]
    }
    lock = {
        "A": {"status": "ok"},
        "B": {"status": "ok_manual"},  # B has no text file
        "C": {"status": "pending_manual"},
        "D": {"status": "rejected_no_text"},
    }
    table = report(_sources(target=4), manifest, lock, tmp_path)
    assert "| 4 | CGTMSE | 4 | 1 | 1 |" in table  # B lacks text: not available; only C pending
    assert "Distance to 500: **499**" in table


def test_KR01_form_pager_posts_the_page_field_and_stops_at_target() -> None:
    posted: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="")
        if request.method == "POST":
            page = request.content.decode().split("=")[1]
            posted.append(page)
            href = f"/Default/ViewFile/?id={page}0_Circular%20{page}.pdf&amp;path=Circular"
            return httpx.Response(200, text=f'<a href="{href}">C{page}</a>')
        return httpx.Response(200, text=INDEX)

    manifest: dict[str, Any] = {"documents": []}
    sources = _sources(target=4, form_pages={"field": "pageNo", "last": 29})
    assert harvest(sources, manifest, {}, _gate(handler)) == 4
    assert posted == ["2", "3"]  # two posts were enough for four documents


def test_KR01_harvested_documents_replace_unfilled_slots() -> None:
    manifest: dict[str, Any] = {"documents": []}
    lock: dict[str, dict[str, Any]] = {}
    ensure_slots(_sources(), manifest, lock)  # 3 PENDING slots
    assert harvest(_sources(), manifest, lock, _gate(_ok)) == 2
    titles = sorted(d["title"] for d in manifest["documents"])
    assert len(titles) == 3 and titles.count("PENDING") == 1
