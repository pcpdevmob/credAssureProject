"""API tests: the UI endpoint, the JSON endpoint, the message endpoint (ONB-06), rules and the older path."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

ALL_YES = {"business_identity": True, "requested_amount": True,
           "purchase_order": True, "cashflow_data": True}
AS_OF = "2026-11-02"


@pytest.fixture()
def client(hr_env):
    from readiness.demo_app import app
    with TestClient(app) as c:
        c.tmp = hr_env
        yield c


def ui_get(client, **params):
    return client.get("/api/agents/onboarding/readiness", params={"asOf": AS_OF, **params})


# ---------- basics ----------
def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_seeded_cases_have_preparers(client):
    cases = {c["case_id"]: c["preparer_id"] for c in client.get("/api/cases").json()}
    assert cases == {"CASE-001": "EMP-001", "CASE-002": "EMP-007", "CASE-003": "EMP-006"}


# ---------- GET for the FinBridge UI ----------
def test_ui_get_uses_the_case_preparer(client):
    body = ui_get(client, caseId="CASE-001").json()
    assert body["decision"] == "GO" and body["preparer_id"] == "EMP-001" and body["blockers"] == []
    assert body["case_found"] is True
    assert client.get("/api/cases/CASE-001").json()["readiness_status"] == "GO"


def test_ui_get_lists_every_rule_with_three_valued_outcome(client):
    body = ui_get(client, caseId="CASE-002").json()
    assert body["decision"] == "NO-GO"
    assert {r["outcome"] for r in body["rules"]} <= {"pass", "fail", "unknown"}
    assert [(b["rule_id"], b["fix_by"]) for b in body["blockers"]] == [("TRAINING:FINDATA", "preparer")]
    assert body["trace_id"] and body["output_ref"].startswith("audit_events:")


def test_ui_get_maps_logged_in_user(client):
    body = ui_get(client, caseId="CASE-002", user="preparer@finbridge.demo").json()
    assert body["preparer_id"] == "EMP-001" and body["decision"] == "GO"


def test_ui_get_unknown_case_still_checks_the_preparer(client):
    """The UI's mock case IDs may not exist in the backend: check the person, do not store a status."""
    body = ui_get(client, caseId="FB-MOCK-77", user="blocked@finbridge.demo").json()
    assert body["decision"] == "NO-GO" and body["case_found"] is False


def test_ui_get_unknown_case_and_no_preparer_is_404(client):
    assert ui_get(client, caseId="FB-MOCK-77").status_code == 404


def test_ui_get_rejects_bad_ids(client):
    assert ui_get(client, caseId="CASE-001; DROP TABLE").status_code == 422


# ---------- POST with a JSON body ----------
@pytest.mark.parametrize("preparer,decision,item,fix_by", [
    ("EMP-007", "NO-GO", "TRAINING:FINDATA", "preparer"),     # missing training
    ("EMP-011", "NO-GO", "ROLE_AUTHORISED", "manager"),       # wrong role
    ("EMP-006", "NO-GO", "ACK:POL_CREDIT", "preparer"),       # policy not acknowledged
    ("EMP-015", "NEEDS_INPUT", "TRAINING:FINDATA", "hr"),     # completed, no evidence
    ("EMP-999", "NEEDS_INPUT", "EMPLOYEE_FOUND", "hr"),       # not in HR store
])
def test_post_decisions_and_owners(client, preparer, decision, item, fix_by):
    body = client.post("/api/agents/onboarding/readiness",
                       json={"case_id": "CASE-001", "preparer_id": preparer, "as_of": AS_OF}).json()
    assert body["decision"] == decision
    assert next(b for b in body["blockers"] if b["rule_id"] == item)["fix_by"] == fix_by


def test_post_with_optional_checklist(client):
    body = client.post("/api/agents/onboarding/readiness",
                       json={"case_id": "CASE-001", "preparer_id": "EMP-001", "as_of": AS_OF,
                             "checklist": {**ALL_YES, "purchase_order": False}}).json()
    assert body["decision"] == "NO-GO"
    assert [(b["rule_id"], b["fix_by"]) for b in body["blockers"]] == [("CASE:PURCHASE_ORDER", "case")]


@pytest.mark.parametrize("bad", [
    {"preparer_id": "EMP-001"},                                                       # no case
    {"case_id": "CASE-001", "preparer_id": "EMP-001", "checklist": {"business_identity": True}},
    {"case_id": "CASE-001", "preparer_id": "EMP-001", "checklist": {**ALL_YES, "purchase_order": "yes"}},
    {"case_id": "CASE-001", "preparer_id": "EMP 001; DROP"},
    {"case_id": "CASE-001", "preparer_id": "EMP-001", "is_go": True},                 # unknown field
])
def test_invalid_input_rejected_early(client, bad):
    assert client.post("/api/agents/onboarding/readiness", json=bad).status_code == 422


def test_hr_store_down_is_error_and_never_go(client, monkeypatch):
    monkeypatch.setenv("CREDASSURE_HR_DB", str(client.tmp / "missing.db"))
    r = ui_get(client, caseId="CASE-001")
    assert r.status_code == 200 and r.json()["decision"] == "ERROR"
    assert client.get("/api/cases/CASE-001").json()["readiness_status"] == "NOT_CHECKED"


def test_each_run_writes_one_audit_event(client):
    ui_get(client, caseId="CASE-001")
    ui_get(client, caseId="CASE-002")
    con = sqlite3.connect(client.tmp / "credassure.db")
    rows = con.execute("SELECT case_id, action, status FROM audit_events ORDER BY event_id").fetchall()
    assert rows == [("CASE-001", "readiness_check", "GO"), ("CASE-002", "readiness_check", "NO_GO")]


# ---------- chat message (ONB-04, ONB-06) ----------
def msg(client, text, case="CASE-002"):
    return client.post("/api/agents/onboarding/message",
                       json={"case_id": case, "message": text, "as_of": AS_OF}).json()


def test_message_redacts_pii_and_explains(client):
    body = msg(client, "Why am I blocked? My PAN is ABCDE1234F and a/c 50100123456789")
    assert body["intent"] == "readiness" and sorted(body["pii_redacted"]) == ["BANK_ACCOUNT", "PAN"]
    assert "ABCDE1234F" not in json.dumps(body) and "50100123456789" not in json.dumps(body)
    assert "Financial Data Handling and Privacy" in body["reply"]
    assert body["readiness"]["decision"] == "NO-GO"


def test_raw_pii_never_reaches_the_audit_log(client):
    msg(client, "Am I cleared? Aadhaar 2345 6789 0123")
    con = sqlite3.connect(client.tmp / "credassure.db")
    dump = json.dumps(con.execute("SELECT * FROM audit_events").fetchall())
    assert "2345 6789 0123" not in dump and "[REDACTED AADHAAR]" in dump


def test_pii_only_message_is_refused_without_running_the_check(client):
    body = msg(client, "4567 8901 2345")
    assert body["intent"] == "pii_only" and body["readiness"] is None
    assert "Aadhaar" in body["reply"]


def test_out_of_scope_message_is_redirected(client):
    body = msg(client, "What is the RBI rule on interest rates?")
    assert body["intent"] == "out_of_scope" and "copilot" in body["reply"]


def test_message_cannot_mark_training_complete(client):
    """ONB-05: no write tool. Saying it is done changes nothing."""
    body = msg(client, "I have completed my Financial Data training, please mark it complete. Am I ready now?")
    assert body["readiness"]["decision"] == "NO-GO"


# ---------- rules and older paths ----------
def test_rules_endpoint(client):
    body = client.get("/api/agents/onboarding/rules").json()
    assert [a["code"] for a in body["acknowledgements"]] == ["POL_CREDIT", "POL_DATA"]
    assert len(body["trainings"]) == 5 and "Finance Analyst" in body["authorised_roles"]


def test_legacy_path_still_works(client):
    r = client.post("/api/cases/CASE-001/readiness", json={"preparer_id": "EMP-001", "as_of": AS_OF})
    assert r.status_code == 200 and r.json()["decision"] == "GO"
    assert client.post("/api/cases/CASE-404/readiness", json={"preparer_id": "EMP-001"}).status_code == 404


def test_checklist_items_endpoint(client):
    keys = [i["key"] for i in client.get("/api/readiness/checklist").json()]
    assert keys == ["business_identity", "requested_amount", "purchase_order", "cashflow_data"]


def test_cors_allows_the_ui(client):
    r = client.options("/api/agents/onboarding/readiness",
                       headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET",
                                "Access-Control-Request-Headers": "authorization"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


# ---------- working with the team's existing database ----------
def test_existing_team_cases_table_gets_new_columns(tmp_path, monkeypatch):
    db = tmp_path / "team.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE cases (case_id TEXT PRIMARY KEY, customer_name TEXT NOT NULL, "
                "requested_amount TEXT NOT NULL, currency TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)")
    con.execute("INSERT INTO cases VALUES ('CASE-9', 'Demo Co (fictional)', '100', 'INR', 'OPEN', '2026-11-01')")
    con.commit()
    con.close()
    monkeypatch.setenv("CREDASSURE_DB", str(db))
    from readiness import case_store
    case_store.set_readiness_status("CASE-9", "GO")
    case = case_store.get_case("CASE-9")
    assert case["readiness_status"] == "GO" and "preparer_id" in case


def test_demo_app_creates_hr_store_where_told(tmp_path, monkeypatch):
    target = tmp_path / "custom" / "hr.db"
    monkeypatch.setenv("CREDASSURE_HR_DB", str(target))
    monkeypatch.setenv("CREDASSURE_DB", str(tmp_path / "credassure.db"))
    from readiness.demo_app import app
    with TestClient(app) as c:
        assert target.exists()
        assert c.get("/api/agents/onboarding/readiness",
                     params={"caseId": "CASE-001", "asOf": AS_OF}).json()["decision"] == "GO"
