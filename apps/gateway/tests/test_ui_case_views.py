"""Plain-language case views (UI thread, 20 Nov): files, readiness and history for case members,
and the created/updated times on the case summary. Read-only routes; scoping as every case read."""

from collections.abc import Callable
from datetime import datetime

from fastapi.testclient import TestClient

Login = Callable[[TestClient, str], dict[str, str]]


def _parses(ts: str) -> bool:
    return datetime.fromisoformat(ts).tzinfo is not None


def test_UI03_case_summary_has_created_and_updated_times(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    h = login(client, "demo.preparer")
    one = client.get(f"/v1/cases/{case_id}", headers=h).json()
    assert _parses(one["created_at"]) and _parses(one["updated_at"])
    listed = next(i for i in client.get("/v1/cases", headers=h).json()["items"])
    assert _parses(listed["created_at"]) and _parses(listed["updated_at"])


def test_UI02_files_lists_latest_upload_per_kind_and_documents_without_kfs_text(
    client: TestClient,
    login: Login,
    new_case: Callable[[TestClient], str],
    upload_demo_files: Callable[[TestClient, str], None],
) -> None:
    case_id = new_case(client)
    h = login(client, "demo.preparer")
    empty = client.get(f"/v1/cases/{case_id}/files", headers=h).json()
    assert [f["uploaded_at"] for f in empty["files"]] == [None] * 7 and empty["documents"] == []
    upload_demo_files(client, case_id)
    body = client.get(f"/v1/cases/{case_id}/files", headers=h).json()
    by = {f["kind"]: f for f in body["files"]}
    assert by["order"]["rows"] == 1 and by["order"]["data"]["currency"] == "INR"
    assert by["costs"]["rows"] == len(by["costs"]["data"]) > 0
    assert {d["kind"] for d in body["documents"]} == {"offer", "kfs"}
    assert "text" not in str(body["documents"])  # the KFS body (lender text, BR-15) is not sent


def test_UI_readiness_shows_rules_with_hr_evidence_after_the_stage_runs(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    case_id = run_case(client)
    r = client.get(f"/v1/cases/{case_id}/readiness", headers=login(client, "demo.preparer"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["decision"] == "GO" and _parses(body["checked_at"])
    assert body["preparer"]["emp_id"] and body["preparer"]["name"]
    rules = {x["rule"]: x for x in body["rules"]}
    assert set(rules) == {"role", "AML-201", "DPDP-101", "FIN-101", "policy_ack"}
    assert all(x["outcome"] == "PASS" for x in rules.values())
    assert rules["FIN-101"]["training"]["expires_on"]
    assert rules["policy_ack"]["policy_ack"]["version"] == "v3"


def test_UI_readiness_before_any_run_has_no_decision(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    body = client.get(
        f"/v1/cases/{case_id}/readiness", headers=login(client, "demo.preparer")
    ).json()
    assert body["decision"] is None and body["rules"] == [] and body["checked_at"] is None


def test_UI_history_for_case_members_hides_hashes_and_free_text_facts(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    case_id = run_case(client)
    r = client.get(f"/v1/cases/{case_id}/history", headers=login(client, "demo.preparer"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["chain_ok"] is True
    types = [e["event_type"] for e in body["events"]]
    assert types[0] == "CASE_CREATED" and "STAGE_COMPLETED" in types
    text = str(body)
    assert "sha256" not in text and "input_hash" not in text and "source_ref" not in text
    for e in body["events"]:
        if e["event_type"] == "FACT_WRITTEN" and e["details"].get("unit") == "json":
            assert "value" not in e["details"]  # narratives stay in the audit log
    creator = body["events"][0]
    assert creator["actor_role"] == "preparer" and creator["actor_name"]


def test_UI_new_views_are_case_scoped(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    other = login(client, "demo.preparer2")  # not this case's preparer, not routed to it
    for path in ("files", "readiness", "history"):
        r = client.get(f"/v1/cases/{case_id}/{path}", headers=other)
        assert r.status_code == 404, (path, r.text)
