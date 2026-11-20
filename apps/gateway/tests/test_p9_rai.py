"""P9 RAI (plan v3.4 §6, OWASP ASI09): approver attestation before approve, the per-case safety
panel, and the source of every narrative and copilot answer for the "AI-generated draft" badge."""

import importlib.util
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

_spec = importlib.util.spec_from_file_location(
    "approvals", Path(__file__).with_name("test_phase10_approvals.py")
)
assert _spec and _spec.loader
approvals = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(approvals)
Login = Callable[[TestClient, str], dict[str, str]]


def test_P9_ASI09_approve_needs_the_attestation_and_records_it(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    approvals._routed(client, case_id, 14_200_000, "director_finance")
    director = login(client, "demo.director")
    r = approvals._approve(client, director, case_id, attested=False)
    assert r.status_code == 422 and r.json()["code"] == "ATTESTATION_REQUIRED", r.text
    assert (
        client.get(f"/v1/cases/{case_id}", headers=director).json()["status"] == "AWAITING_APPROVAL"
    )
    r = approvals._approve(client, director, case_id)
    assert r.status_code == 200, r.text
    audit = client.get(f"/v1/cases/{case_id}/audit", headers=login(client, "demo.evaluator")).json()
    assert "DECISION_RECORDED" in [e["event_type"] for e in audit["events"]]
    svc: Any = client.app.state.services  # type: ignore[attr-defined]
    from credassure.ledger import reads
    from credassure.ledger.session import transaction

    with transaction(svc.engine) as s:
        payloads = [
            e.payload
            for e in reads.audit_events(s, "default", case_id)
            if e.event_type == "DECISION_RECORDED"
        ]
    assert payloads[-1]["attested"] is True


def test_P9_reject_needs_no_attestation(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    approvals._routed(client, case_id, 14_200_000, "director_finance")
    director = login(client, "demo.director")
    version = client.get(f"/v1/cases/{case_id}", headers=director).json()["row_version"]
    r = client.post(
        f"/v1/cases/{case_id}/decision",
        json={"decision": "reject", "comment": "no", "expected_version": version},
        headers=director,
    )
    assert r.status_code == 200, r.text


def test_P9_safety_panel_lists_guardrail_events_without_text(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    h = login(client, "demo.preparer")
    body = b"invoice_id,customer,amount,due_week,expected_week\nINV-1,BQZPK4821M,100,3,4\n"
    r = client.post(
        f"/v1/cases/{case_id}/files",
        params={"kind": "receivables"},
        files={"file": ("receivables.csv", body, "text/csv")},
        headers=h,
    )
    assert r.status_code == 422
    client.post(
        f"/v1/cases/{case_id}/chat", json={"message": "My PAN is BQZPK4821M, fee?"}, headers=h
    )
    panel = client.get(f"/v1/cases/{case_id}/safety", headers=h)
    assert panel.status_code == 200, panel.text
    data = panel.json()
    assert data["counts"].get("block") == 1 and data["counts"].get("redact") == 1
    assert {e["rule_id"] for e in data["events"]} >= {
        "R1.upload_pii_refused",
        "R1.chat_pii_redacted",
    }
    assert "BQZPK4821M" not in panel.text


def test_P9_ai_badge_sources_for_narratives_and_chat(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    h = login(client, "demo.preparer")
    client.post(f"/v1/agents/onboarding/cases/{case_id}/run", headers=h)
    stages = client.get(f"/v1/cases/{case_id}", headers=h).json()["stages"]
    onb = next(s for s in stages if s["stage"] == "onboarding")
    assert onb["narrative_source"] in ("model", "template")
    chat = client.post(
        f"/v1/cases/{case_id}/chat", json={"message": "How is the fee charged?"}, headers=h
    )
    assert chat.json()["source"] in ("model", "code")
