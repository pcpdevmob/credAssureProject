"""BRD §14 / Phase 8 acceptance: the demo case run through the API is one trace (scope #15)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from credassure.observability.tracing import capture

DEMO = Path(__file__).resolve().parents[2] / "data" / "frozen" / "v1" / "cases" / "CA-2026-0001"
KINDS = ("order", "opening_position", "costs", "receipts", "receivables", "payables", "inventory")


def test_OBJ08_demo_case_run_and_approval_share_one_trace(
    make_client: Callable[[bool], tuple[TestClient, Any]],
    login: Callable[[TestClient, str], dict[str, str]],
    upload_offers: Callable[[TestClient, str, dict[str, str]], None],
) -> None:
    client, _ = make_client(False)
    prep = login(client, "demo.preparer")
    case_id = client.post(
        "/v1/cases",
        json={
            "msme_name": "Demo Electronics Pvt Ltd",
            "order_ref": "PO-CA-2026-0001",
            "order_value_paise": 3_20_00_000_00,
            "indicative_amount_paise": 2_00_00_000_00,
            "due_date": "2027-05-15",
        },
        headers=prep,
    ).json()["case_id"]
    for kind in KINDS:
        name = f"{kind}.json" if kind in ("order", "opening_position") else f"{kind}.csv"
        media = "application/json" if name.endswith(".json") else "text/csv"
        r = client.post(
            f"/v1/cases/{case_id}/files",
            params={"kind": kind},
            files={"file": (name, (DEMO / name).read_bytes(), media)},
            headers=prep,
        )
        assert r.status_code == 201, r.text
    upload_offers(client, case_id, prep)
    with capture() as spans:
        assert client.post(f"/v1/cases/{case_id}/run", headers=prep).status_code == 202
        version = client.get(f"/v1/cases/{case_id}", headers=prep).json()["row_version"]
        director = login(client, "demo.director")
        r = client.post(
            f"/v1/cases/{case_id}/decision",
            json={
                "decision": "approve",
                "attested": True,
                "comment": "ok",
                "expected_version": version,
            },
            headers=director,
        )
        assert r.status_code == 200, r.text
    traced = [s for s in spans if s.get("case_id") == case_id]
    assert {s["name"] for s in traced} >= {"plan", "stage", "route", "decision"}
    assert len({s["trace_id"] for s in traced}) == 1
    # ADR 0029 (P3): rail events are spans in the same trace
    rails = {(s["rail"], s["rule_id"], s["action"]) for s in traced if s["name"] == "guardrail"}
    assert ("R3", "R3.tool_allowed", "pass") in rails
    assert ("R4", "R4.critic_passed", "pass") in rails
