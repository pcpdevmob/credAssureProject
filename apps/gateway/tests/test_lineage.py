"""Scope #33: GET /v1/cases/{id}/facts/{key}/lineage — where a figure came from (OBJ-08).

Tests drive the HTTP API as a UI would (API-01). Same access rules as the other case routes
(SUP-08); agent ledger-prefix rules do not apply to reading lineage."""

from __future__ import annotations

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from credassure.ledger import reads, session
from credassure.ledger.store import SqlLedger

ROOT = Path(__file__).resolve().parents[3]
Login = Callable[[TestClient, str], dict[str, str]]
KEYS = {
    "case_id", "key", "version", "latest_version", "superseded_by", "value", "unit", "created_at",
    "source_type", "source_ref", "engine", "input_hash", "files", "inputs", "passages",
    "producer", "audit",
}  # fmt: skip


def _lineage(client: Any, h: dict[str, str], case_id: str, key: str, **params: Any) -> Any:
    return client.get(f"/v1/cases/{case_id}/facts/{key}/lineage", params=params, headers=h)


def test_33_lineage_of_recommended_amount(client: Any, login: Login, run_case: Any) -> None:
    case_id = run_case(client)
    h = login(client, "demo.preparer")
    r = _lineage(client, h, case_id, "wc.recommended_amount")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["value"]["display"].startswith("₹") and isinstance(body["value"]["paise"], int)
    assert body["engine"] == {"name": "engines.cashflow", "version": "1"}
    assert len(body["input_hash"]) == 64 and body["superseded_by"] is None
    with session.transaction(session.case_engine(client.db)) as s:
        uploaded = {f.sha256 for f in reads.case_files(s, "default", case_id)}
        runs = reads.stage_runs(s, "default", case_id)
    files = body["files"]
    kinds = {f["kind"] for f in files}
    assert {"order", "opening_position", "costs", "receipts"} <= kinds
    assert all(f["sha256"] in uploaded and f["name"] for f in files)
    wc_traces = {r.trace_id for r in runs if r.stage == "working_capital"}
    assert body["producer"]["agent"] == "working_capital"
    assert body["producer"]["stage"] == "working_capital"
    assert body["producer"]["trace_id"] in wc_traces
    assert body["audit"]["seq"] > 0 and body["audit"]["ts"]


def test_33_reference_rate_fact_lists_its_passage(client: Any, login: Login) -> None:
    data = ROOT / "data/frozen/v1"
    h = login(client, "demo.preparer")
    new = {
        "msme_name": "Demo Electronics Pvt Ltd",
        "order_ref": "PO-LIN",
        "order_value_paise": 3_20_00_000_00,
        "indicative_amount_paise": 2_00_00_000_00,
        "due_date": "2027-05-15",
    }
    case_id = client.post("/v1/cases", json=new, headers=h).json()["case_id"]
    uploads = [(p.stem, p) for p in sorted((data / "cases/CA-2026-0003").glob("*.*"))]
    for offer in sorted((data / "offers/CA-2026-0003").glob("*.v1.json")):  # OF-03-B is EBLR
        doc = json.loads(offer.read_text())["kfs_doc_id"]
        uploads += [("offer", offer), ("kfs", data / f"kfs/{doc}.md")]
        uploads += [("kfs", data / f"kfs/{doc}-SCH.md")]
    mime = {".json": "application/json", ".csv": "text/csv", ".md": "text/markdown"}
    for kind, path in uploads:
        if kind == "expected":
            continue
        r = client.post(
            f"/v1/cases/{case_id}/files",
            params={"kind": kind},
            files={"file": (path.name, path.read_bytes(), mime[path.suffix])},
            headers=h,
        )
        assert r.status_code == 201, (kind, r.text)
    for stage in ("onboarding", "working-capital", "lendwise"):
        assert client.post(f"/v1/agents/{stage}/cases/{case_id}/run", headers=h).status_code == 202
    r = _lineage(client, h, case_id, "lw.reference_rate.repo")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [p["doc_id"] for p in body["passages"]] == ["R-RATE-02-REPO"]
    assert body["files"] == [] and body["value"]["paise"] is None
    assert body["value"]["display"] == "0.055"


def test_33_old_version_reports_superseded_by(client: Any, login: Login, run_case: Any) -> None:
    case_id = run_case(client)
    ledger = SqlLedger(session.case_engine(client.db), "default")
    v1 = ledger.get(case_id, "wc.recommended_amount")
    assert v1 is not None
    ledger.put_fact(
        case_id,
        "wc.recommended_amount",
        Decimal(v1) + 100,
        unit="INR",
        source_type="case_file",
        source_ref="case_files:order@x",
        produced_by="engines.cashflow@1",
    )
    h = login(client, "demo.preparer")
    old = _lineage(client, h, case_id, "wc.recommended_amount", version=1).json()
    new = _lineage(client, h, case_id, "wc.recommended_amount").json()
    assert (old["version"], old["latest_version"], old["superseded_by"]) == (1, 2, 2)
    assert (new["version"], new["superseded_by"]) == (2, None)
    assert new["producer"] == {
        "agent": None,
        "stage": None,
        "trace_id": None,
    }  # written outside a stage


def test_33_unknown_key_404_problem_json(client: Any, login: Login, run_case: Any) -> None:
    case_id = run_case(client)
    h = login(client, "demo.preparer")
    for r in (
        _lineage(client, h, case_id, "wc.nope"),
        _lineage(client, h, case_id, "wc.recommended_amount", version=99),
    ):
        assert r.status_code == 404
        assert r.headers["content-type"].startswith("application/problem+json")


def test_SUP08_lineage_other_preparer_gets_404(client: Any, login: Login, run_case: Any) -> None:
    case_id = run_case(client)
    r = _lineage(client, login(client, "demo.preparer2"), case_id, "wc.recommended_amount")
    assert r.status_code == 404
    assert "1,42" not in r.text and "engines" not in r.text


def test_33_evaluator_and_approver_read_without_agent_prefix_check(
    client: Any, login: Login, run_case: Any
) -> None:
    case_id = run_case(client)
    for user in ("demo.evaluator", "demo.director"):
        r = _lineage(client, login(client, user), case_id, "onb.gate")
        assert r.status_code == 200, (user, r.text)


def test_contract_lineage_shape_and_openapi_path(client: Any, login: Login, run_case: Any) -> None:
    case_id = run_case(client)
    body = _lineage(client, login(client, "demo.preparer"), case_id, "wc.gate").json()
    assert set(body) == KEYS
    assert set(body["value"]) == {"text", "paise", "display"}
    assert set(body["producer"]) == {"agent", "stage", "trace_id"}
    assert set(body["audit"]) == {"seq", "actor", "ts"}
    spec = json.loads((ROOT / "openapi.json").read_text())
    op = spec["paths"]["/v1/cases/{case_id}/facts/{key}/lineage"]["get"]
    assert "$ref" in json.dumps(op["responses"]["200"])  # typed for the generated client


def test_33_version_out_of_range_is_422_not_500(client: Any, login: Login, run_case: Any) -> None:
    case_id = run_case(client)
    r = _lineage(client, login(client, "demo.preparer"), case_id, "wc.gate", version=10**20)
    assert r.status_code == 422
    assert r.headers["content-type"].startswith("application/problem+json")
