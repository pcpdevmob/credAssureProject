"""Full demo case through the API with FakeLLM, LLM on and off (scope #15, API-01, ADR 0003 §2).

SUP-01 fixed plan end to end → LW-11 offers ranked → APR-02 Director route for ₹1,42,00,000 →
APR-05 maker-checker → APR-04 decision → OBJ-08 audit chain → UI-08 report with trace IDs.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

DEMO = Path(__file__).resolve().parents[2] / "data" / "frozen" / "v1" / "cases" / "CA-2026-0001"
KINDS = ("order", "opening_position", "costs", "receipts", "receivables", "payables", "inventory")


@pytest.mark.parametrize("llm_enabled", [True, False])
def test_scope15_SUP01_APR02_demo_case_end_to_end(
    make_client: Callable[[bool], tuple[TestClient, Any]],
    login: Callable[[TestClient, str], dict[str, str]],
    upload_offers: Callable[[TestClient, str, dict[str, str]], None],
    llm_enabled: bool,
) -> None:
    client, llm = make_client(llm_enabled)
    prep = login(client, "demo.preparer")

    r = client.post(
        "/v1/cases",
        json={
            "msme_name": "Demo Electronics Pvt Ltd",
            "order_ref": "PO-CA-2026-0001",
            "order_value_paise": 3_20_00_000_00,
            "indicative_amount_paise": 2_00_00_000_00,
            "due_date": "2027-05-15",
        },
        headers=prep,
    )
    assert r.status_code == 201, r.text
    case_id = r.json()["case_id"]

    for kind in KINDS:
        name = f"{kind}.json" if kind in ("order", "opening_position") else f"{kind}.csv"
        mime = "application/json" if name.endswith(".json") else "text/csv"
        up = client.post(
            f"/v1/cases/{case_id}/files",
            params={"kind": kind},
            files={"file": (name, (DEMO / name).read_bytes(), mime)},
            headers=prep,
        )
        assert up.status_code == 201, (kind, up.text)
    upload_offers(client, case_id, prep)

    run = client.post(f"/v1/cases/{case_id}/run", headers=prep)
    assert run.status_code == 202, run.text
    job = client.get(run.json()["status_url"], headers=prep).json()
    assert job["status"] == "succeeded"
    assert job["outcome"] == "AWAITING_APPROVAL"

    case = client.get(f"/v1/cases/{case_id}", headers=prep).json()
    assert case["route"] == "director_finance"
    funding = client.get(f"/v1/cases/{case_id}/funding", headers=prep).json()
    assert funding["recommended_amount"]["paise"] == 1_42_00_000_00
    offers = client.get(f"/v1/cases/{case_id}/offers", headers=prep).json()
    assert offers["gate"] == "GO" and offers["ranking"] == ["OF-01-B", "OF-01-A"]  # BRD App. A

    decision = {"decision": "approve", "comment": "ok", "expected_version": case["row_version"]}
    assert (
        client.post(f"/v1/cases/{case_id}/decision", json=decision, headers=prep).status_code == 403
    )

    director = login(client, "demo.director")
    version = client.get(f"/v1/cases/{case_id}", headers=director).json()["row_version"]
    approved = client.post(
        f"/v1/cases/{case_id}/decision",
        json={"decision": "approve", "comment": "approved", "expected_version": version},
        headers=director,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"

    audit = client.get(f"/v1/cases/{case_id}/audit", headers=login(client, "demo.evaluator"))
    assert audit.status_code == 200
    assert audit.json()["chain_ok"] is True

    report = client.get(f"/v1/cases/{case_id}/report", params={"fmt": "md"}, headers=prep)
    assert report.status_code == 200
    trace_ids = [s["trace_id"] for s in case["stages"]]
    assert trace_ids and all(t in report.text for t in trace_ids)

    assert (llm is not None and len(llm.calls) > 0) == llm_enabled
