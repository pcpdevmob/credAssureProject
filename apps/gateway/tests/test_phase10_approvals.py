"""Phase 10 approvals: step-up re-auth above ₹1.5 crore (NFR-07), maker-checker (APR-05), internal
only (APR-06). The routed amount is the validated wc.recommended_amount (Q-02)."""

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

PASSWORD = "fixture-password-123"  # conftest.PASSWORD (importlib mode: no import from conftest)
Login = Callable[[TestClient, str], dict[str, str]]


def _routed(client: Any, case_id: str, rupees: int, route: str) -> None:
    """A case whose Working Capital gate is GO at `rupees`, routed to `route` (no graph run)."""
    led = client.app.state.services.ledger
    for key, value, unit in (("wc.gate", "GO", "enum"), ("wc.recommended_amount", rupees, "INR")):
        led.put_fact(
            case_id, key, value, unit=unit, source_type="test", source_ref="t", produced_by="t"
        )
    led.route(case_id, route)


def _approve(client: TestClient, h: dict[str, str], case_id: str, **extra: Any) -> Any:
    version = client.get(f"/v1/cases/{case_id}", headers=h).json()["row_version"]
    body = {"decision": "approve", "comment": "ok", "expected_version": version, **extra}
    return client.post(f"/v1/cases/{case_id}/decision", json=body, headers=h)


def _events(client: TestClient, login: Login, case_id: str) -> list[str]:
    audit = client.get(f"/v1/cases/{case_id}/audit", headers=login(client, "demo.evaluator"))
    return [e["event_type"] for e in audit.json()["events"]]


def test_NFR07_vp_approval_above_threshold_needs_step_up(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    _routed(client, case_id, 15_000_001, "vp_finance")  # ₹1,50,00,001 (APR-01)
    vp = login(client, "demo.vp")
    r = _approve(client, vp, case_id)
    assert r.status_code == 403, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == "STEP_UP_REQUIRED"
    assert client.get(f"/v1/cases/{case_id}", headers=vp).json()["status"] == "AWAITING_APPROVAL"

    r = _approve(client, vp, case_id, password="wrong-password")
    assert r.status_code == 403 and r.json()["code"] == "STEP_UP_REQUIRED"
    assert "STEP_UP_FAILED" in _events(client, login, case_id)

    r = _approve(client, vp, case_id, password=PASSWORD)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"
    events = _events(client, login, case_id)
    assert events.index("STEP_UP_VERIFIED") < events.index("DECISION_RECORDED")


def test_NFR07_director_below_threshold_needs_no_step_up(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    """The demo path: ₹1,42,00,000 → Director approves with no re-auth (demo-script 8:00)."""
    case_id = new_case(client)
    _routed(client, case_id, 14_200_000, "director_finance")
    r = _approve(client, login(client, "demo.director"), case_id)
    assert r.status_code == 200, r.text


def test_NFR07_reject_above_threshold_needs_no_step_up(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    _routed(client, case_id, 15_000_001, "vp_finance")
    vp = login(client, "demo.vp")
    version = client.get(f"/v1/cases/{case_id}", headers=vp).json()["row_version"]
    body = {"decision": "reject", "comment": "no", "expected_version": version}
    assert client.post(f"/v1/cases/{case_id}/decision", json=body, headers=vp).status_code == 200


def test_NFR07_step_up_flag_off_skips_re_auth(
    make_client: Callable[..., Any], login: Login, new_case: Callable[[TestClient], str]
) -> None:
    client = make_client(approval_step_up=False)
    case_id = new_case(client)
    _routed(client, case_id, 15_000_001, "vp_finance")
    assert _approve(client, login(client, "demo.vp"), case_id).status_code == 200


def test_NFR07_step_up_failures_are_rate_limited(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    _routed(client, case_id, 15_000_001, "vp_finance")
    vp = login(client, "demo.vp")
    codes = [_approve(client, vp, case_id, password="bad").status_code for _ in range(6)]
    assert codes[:5] == [403] * 5
    assert codes[5] == 429
    # the right password is refused too while limited: no guessing through the limit
    assert _approve(client, vp, case_id, password=PASSWORD).status_code == 429


def test_APR05_preparer_cannot_approve_even_with_password(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    _routed(client, case_id, 15_000_001, "vp_finance")
    r = _approve(client, login(client, "demo.preparer"), case_id, password=PASSWORD)
    assert r.status_code == 403
    assert r.json()["code"] == "FORBIDDEN"


def test_APR06_decision_schema_has_no_lender_acceptance(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()["components"]["schemas"]["Decision"]
    assert schema["properties"]["decision"]["enum"] == ["approve", "reject", "return"]
    assert schema["properties"]["password"]["anyOf"][0]["writeOnly"] is True  # never echoed


def test_NFR07_step_up_required_when_validated_amount_unknown(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    """Fail closed: no GO funding gate or no amount means the password is required."""
    case_id = new_case(client)
    client.app.state.services.ledger.route(case_id, "director_finance")  # type: ignore[attr-defined]
    r = _approve(client, login(client, "demo.director"), case_id)
    assert r.status_code == 403 and r.json()["code"] == "STEP_UP_REQUIRED"
