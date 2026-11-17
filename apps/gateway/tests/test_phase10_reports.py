"""Phase 10 reports: rendering against sections.yaml (UI-08, VER-04, #10), versioning and staleness
(#6, ADR 0003 §3: a stale report blocks approve), figures with ledger keys for the provenance
drawer (#33), /offers after a re-upload (UI-05)."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from credassure.reports.sections import required_sections

Login = Callable[[TestClient, str], dict[str, str]]
FROZEN = Path(__file__).resolve().parents[3] / "data" / "frozen" / "v1"


def _report(client: TestClient, h: dict[str, str], case_id: str, **q: Any) -> Any:
    r = client.get(f"/v1/cases/{case_id}/report", params={"fmt": "json", **q}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _put(client: Any, case_id: str, key: str, value: Any) -> None:
    client.app.state.services.ledger.put_fact(
        case_id, key, value, unit="text", source_type="test", source_ref="t", produced_by="t"
    )


def test_UI08_VER04_routed_case_has_report_v1_with_every_section(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    case_id = run_case(client)
    h = login(client, "demo.preparer")
    rep = _report(client, h, case_id)
    assert rep["version"] == 1  # written when the case was routed
    assert rep["stale"] is False and rep["reasons"] == []
    assert [s["title"] for s in rep["sections"]] == list(required_sections())
    md = client.get(f"/v1/cases/{case_id}/report", headers=h).text
    for title in required_sections():
        assert f"## {title}" in md
    assert "₹1,42,00,000" in md
    assert "Approval is internal" in md


def test_scope33_report_figures_carry_ledger_keys_lineage_resolves(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    case_id = run_case(client)
    h = login(client, "demo.preparer")
    rep = _report(client, h, case_id)
    figures = [(s, f) for s in rep["sections"] for f in s["figures"]]
    assert any(f["key"] == "wc.recommended_amount" for _, f in figures)
    for section, f in figures:
        assert section["text"][f["start"] : f["end"]] == f["display"]
        r = client.get(
            f"/v1/cases/{case_id}/facts/{f['key']}/lineage",
            params={"version": f["version"]},
            headers=h,
        )
        assert r.status_code == 200, (f, r.text)


def test_scope6_changed_fact_makes_report_stale_until_a_new_version(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    case_id = run_case(client)
    h = login(client, "demo.preparer")
    _put(client, case_id, "wc.peak_week", "10")
    rep = _report(client, h, case_id)
    assert rep["stale"] is True
    assert "working_capital" in rep["reasons"]
    md = client.get(f"/v1/cases/{case_id}/report", headers=h)
    assert md.headers["X-Report-Stale"] == "true"
    assert "stale" in md.text.splitlines()[2].lower()

    r = client.post(f"/v1/cases/{case_id}/report", headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 2 and r.json()["stale"] is False
    assert _report(client, h, case_id)["stale"] is False
    old = _report(client, h, case_id, version=1)
    assert old["version"] == 1
    assert old["pinned"]["wc.peak_week"] < _report(client, h, case_id)["pinned"]["wc.peak_week"]


def test_scope6_regenerating_a_fresh_report_keeps_its_version(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    case_id = run_case(client)
    h = login(client, "demo.preparer")
    assert client.post(f"/v1/cases/{case_id}/report", headers=h).json()["version"] == 1


def _stale_inbox(client: Any, login: Login, run_case: Callable[[TestClient], str]) -> Any:
    case_id = run_case(client)
    _put(client, case_id, "lw.negotiation.status", "sent")  # a figure changed after routing
    d = login(client, "demo.director")
    inbox = client.get(f"/v1/cases/{case_id}/inbox", headers=d).json()
    assert "report_stale" in inbox["warnings"]
    return case_id, d, inbox


def test_scope6_UI07_stale_report_blocks_approve_until_regenerated(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    """Phase 10b (ADR 0003 §3, superseding decision 1(a)): approve answers 409 problem+json;
    the preparer regenerates (v2) and the same approval then goes through."""
    case_id, d, inbox = _stale_inbox(client, login, run_case)
    body = {"decision": "approve", "comment": "ok", "expected_version": inbox["row_version"]}
    r = client.post(f"/v1/cases/{case_id}/decision", json=body, headers=d)
    assert r.status_code == 409, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "REPORT_STALE" and "regenerate" in r.json()["detail"]
    assert client.get(f"/v1/cases/{case_id}", headers=d).json()["status"] == "AWAITING_APPROVAL"
    p = login(client, "demo.preparer")
    regen = client.post(f"/v1/cases/{case_id}/report", headers=p)
    assert regen.status_code == 201 and regen.json()["version"] == 2
    inbox = client.get(f"/v1/cases/{case_id}/inbox", headers=d).json()
    assert "report_stale" not in inbox["warnings"]
    body["expected_version"] = inbox["row_version"]
    assert client.post(f"/v1/cases/{case_id}/decision", json=body, headers=d).status_code == 200


def test_scope6_approve_names_the_report_version_the_approver_saw(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    """Security review S1: the Director saw v1; the preparer regenerates to v2; an approve that
    still names v1 is refused, and one that names v2 goes through."""
    case_id, d, inbox = _stale_inbox(client, login, run_case)
    seen = inbox["report_version"]
    assert (
        client.post(f"/v1/cases/{case_id}/report", headers=login(client, "demo.preparer")).json()[
            "version"
        ]
        == seen + 1
    )
    fresh = client.get(f"/v1/cases/{case_id}/inbox", headers=d).json()
    body = {"decision": "approve", "comment": "ok", "expected_version": fresh["row_version"]}
    old = client.post(
        f"/v1/cases/{case_id}/decision", json={**body, "report_version": seen}, headers=d
    )
    assert old.status_code == 409 and old.json()["code"] == "REPORT_STALE"
    new = {**body, "report_version": fresh["report_version"]}
    assert client.post(f"/v1/cases/{case_id}/decision", json=new, headers=d).status_code == 200


def test_scope6_UI07_stale_report_still_allows_reject_and_return(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    for decision, stage in (("reject", None), ("return", "lendwise")):
        case_id, d, inbox = _stale_inbox(client, login, run_case)
        body = {"decision": decision, "comment": "no", "expected_version": inbox["row_version"]}
        if stage:
            body["return_stage"] = stage
        r = client.post(f"/v1/cases/{case_id}/decision", json=body, headers=d)
        assert r.status_code == 200, (decision, r.text)


def test_UI05_offer_reupload_makes_offers_stale_not_the_old_comparison(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    case_id = run_case(client)
    h = login(client, "demo.preparer")
    assert client.get(f"/v1/cases/{case_id}/offers", headers=h).json()["stale"] is False
    d = login(client, "demo.director")  # uploads are locked while awaiting approval: return first
    version = client.get(f"/v1/cases/{case_id}", headers=d).json()["row_version"]
    body = {"decision": "return", "return_stage": "lendwise", "comment": "new KFS",
            "expected_version": version}  # fmt: skip
    assert client.post(f"/v1/cases/{case_id}/decision", json=body, headers=d).status_code == 200
    path = sorted((FROZEN / "offers" / "CA-2026-0001").glob("*.v1.json"))[0]
    changed = json.dumps(json.loads(path.read_text()), indent=4).encode()  # same offer, new bytes
    r = client.post(
        f"/v1/cases/{case_id}/files",
        params={"kind": "offer"},
        files={"file": (path.name, changed, "application/json")},
        headers=h,
    )
    assert r.status_code == 201, r.text
    view = client.get(f"/v1/cases/{case_id}/offers", headers=h).json()
    assert view["stale"] is True
    assert view["source"] == "stale"
    assert "re-run LendWise" in view["message"]
    assert view["offers"] == [] and view["ranking"] == []
    rep = _report(client, h, case_id)
    assert rep["stale"] is True and "upload:offer" in rep["reasons"]
    job = client.post(f"/v1/cases/{case_id}/run", headers=h).json()  # LendWise re-runs on it
    assert client.get(job["status_url"], headers=h).json()["outcome"] == "AWAITING_APPROVAL"
    fresh = client.get(f"/v1/cases/{case_id}/offers", headers=h).json()
    assert fresh["stale"] is False and fresh["offers"]
    assert _report(client, h, case_id)["stale"] is False  # routed again: a new version


def test_scope6_case_without_a_version_renders_a_draft(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    rep = _report(client, login(client, "demo.preparer"), case_id)
    assert rep["version"] is None
    assert rep["stale"] is True and rep["reasons"] == ["no_version"]
    assert [s["title"] for s in rep["sections"]] == list(required_sections())


def test_scope6_only_the_preparer_creates_a_report_version(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    case_id = run_case(client)
    r = client.post(f"/v1/cases/{case_id}/report", headers=login(client, "demo.director"))
    assert r.status_code == 403


def test_UI08_html_report_is_escaped_and_locked_down(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    case_id = run_case(client)
    r = client.get(
        f"/v1/cases/{case_id}/report",
        params={"fmt": "html"},
        headers=login(client, "demo.preparer"),
    )
    assert r.headers["content-security-policy"].startswith("default-src 'none'")
    assert "<script" not in r.text.lower()
    assert "## Approval is internal" in r.text  # Markdown inside an escaped <pre>


def test_VER04_missing_section_blocks_the_report(
    client: TestClient,
    login: Login,
    run_case: Callable[[TestClient], str],
    monkeypatch: Any,
) -> None:
    """VER-04, #10: a report that lacks a required section is never served (fail closed)."""
    case_id = run_case(client)
    from credassure.gateway import report

    monkeypatch.setattr(
        report, "required_sections", lambda: (*required_sections(), "Covenant schedule")
    )
    r = client.get(f"/v1/cases/{case_id}/report", headers=login(client, "demo.preparer"))
    assert r.status_code == 500
    assert r.headers["content-type"].startswith("application/problem+json")
    assert "Covenant" not in r.text  # no internals in the problem body
