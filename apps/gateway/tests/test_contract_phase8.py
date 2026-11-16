"""Phase 8b contract tests: every /v1 route a UI calls (API-01, ADR 0004, phase8-api-spec.md).

Requirement IDs: API-01, UI-01..03, UI-07, UI-08, SUP-02, SUP-03, SUP-08, APR-02, APR-04, APR-05,
NFR-03 (quota), NFR-04 (rate limit), NFR-07 (auth), OBJ-08 (audit), scope #16, #28, #47, #50.
Known answers come from the placeholder WC fact (₹1,42,00,000, spec) and the frozen demo files.
"""

import hashlib
import re
import sqlite3
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response

PROBLEM_KEYS = {"type", "title", "status", "detail", "code", "instance"}
RUN_STAGES = ("onboarding", "working_capital", "lendwise", "critic")


def _problem(r: Response, status: int, code: str | None = None) -> dict[str, Any]:
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    body: dict[str, Any] = r.json()
    assert body.keys() >= PROBLEM_KEYS
    assert body["status"] == status
    if code is not None:
        assert body["code"] == code
    return body


def _case(client: TestClient, h: dict[str, str], case_id: str) -> dict[str, Any]:
    r = client.get(f"/v1/cases/{case_id}", headers=h)
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _attempts(case: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for s in case["stages"]:
        out[s["stage"]] = max(out.get(s["stage"], 0), s["attempt"])
    return out


def _decide(
    client: TestClient, h: dict[str, str], case_id: str, decision: str, version: int, **extra: Any
) -> Response:
    body = {"decision": decision, "comment": "test", "expected_version": version, **extra}
    return client.post(f"/v1/cases/{case_id}/decision", json=body, headers=h)


def _csv_upload(client: TestClient, h: dict[str, str], case_id: str, name: str, data: bytes,
                mime: str = "text/csv", kind: str = "costs") -> Response:  # fmt: skip
    return client.post(
        f"/v1/cases/{case_id}/files",
        params={"kind": kind},
        files={"file": (name, data, mime)},
        headers=h,
    )


@pytest.fixture
def fx(
    make_client: Callable[..., Any],
    client: Any,
    login: Callable[[TestClient, str], dict[str, str]],
    new_case: Callable[[TestClient], str],
    upload_demo_files: Callable[[TestClient, str], None],
    run_case: Callable[[TestClient], str],
) -> SimpleNamespace:
    return SimpleNamespace(
        make_client=make_client,
        client=client,
        login=lambda u, c=None: login(c or client, u),
        new_case=lambda c=None: new_case(c or client),
        upload=lambda case_id, c=None: upload_demo_files(c or client, case_id),
        run_case=lambda c=None: run_case(c or client),
    )


# --- RFC 9457 ----------------------------------------------------------------------------------


def _bad_costs() -> bytes:
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / "data/frozen/v1/cases/CA-2026-0001/costs.csv"
    lines = src.read_text(encoding="utf-8").splitlines()
    week, category, _ = lines[2].split(",")  # data row 2 (header is line 0)
    lines[2] = f"{week},{category},abc"
    return ("\n".join(lines) + "\n").encode()


def _s401(fx: SimpleNamespace) -> Response:
    return fx.client.get("/v1/me")


def _s403(fx: SimpleNamespace) -> Response:
    return fx.client.post("/v1/cases", json={}, headers=fx.login("demo.director"))


def _s404(fx: SimpleNamespace) -> Response:
    return fx.client.get("/v1/cases/CA-2099-9999", headers=fx.login("demo.preparer"))


def _s409(fx: SimpleNamespace) -> Response:
    case_id = fx.run_case()
    h = fx.login("demo.director")
    version = _case(fx.client, h, case_id)["row_version"]
    return _decide(fx.client, h, case_id, "approve", version - 1)


def _s413(fx: SimpleNamespace) -> Response:
    big = b"week,category,amount\n" + b"1,components,1000\n" * 170_000  # ~3 MB
    return _csv_upload(fx.client, fx.login("demo.preparer"), fx.new_case(), "costs.csv", big)


def _s415(fx: SimpleNamespace) -> Response:
    xlsx = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return _csv_upload(
        fx.client, fx.login("demo.preparer"), fx.new_case(), "costs.xlsx", b"PK\x03\x04", xlsx
    )


def _s422(fx: SimpleNamespace) -> Response:
    return _csv_upload(
        fx.client, fx.login("demo.preparer"), fx.new_case(), "costs.csv", _bad_costs()
    )


def _s429(fx: SimpleNamespace) -> Response:
    c = fx.make_client(rate_limit="3/minute")
    h = fx.login("demo.preparer", c)
    return [c.get("/v1/me", headers=h) for _ in range(4)][-1]


def _s501(fx: SimpleNamespace) -> Response:
    return fx.client.post("/v1/eval/runs", json={}, headers=fx.login("demo.evaluator"))


@pytest.mark.parametrize(
    ("status", "code", "scenario"),
    [
        (401, "UNAUTHENTICATED", _s401),
        (403, "FORBIDDEN", _s403),
        (404, "NOT_FOUND", _s404),
        (409, "CONFLICT", _s409),
        (413, "PAYLOAD_TOO_LARGE", _s413),
        (415, "UNSUPPORTED_MEDIA_TYPE", _s415),
        (422, "VALIDATION_FAILED", _s422),
        (429, "RATE_LIMITED", _s429),
        (501, "NOT_IMPLEMENTED", _s501),
    ],
)
def test_API01_errors_are_rfc9457_problem_json(
    fx: SimpleNamespace, status: int, code: str, scenario: Callable[[SimpleNamespace], Response]
) -> None:
    r = scenario(fx)
    _problem(r, status, code)
    assert r.headers["X-Request-ID"]


def test_API01_every_response_carries_x_request_id(fx: SimpleNamespace) -> None:
    h = fx.login("demo.preparer")
    case_id = fx.new_case()
    responses = [
        fx.client.get("/v1/health/live"),
        fx.client.get("/v1/me"),
        fx.client.get("/v1/me", headers=h),
        fx.client.get(f"/v1/cases/{case_id}", headers=h),
        fx.client.get("/v1/cases/CA-2099-9999", headers=h),
        fx.client.post(f"/v1/cases/{case_id}/run", headers=h),
    ]
    assert all(r.headers.get("X-Request-ID") for r in responses)


# --- Auth (NFR-07) --------------------------------------------------------------------------------


def test_NFR07_login_returns_bearer_token(fx: SimpleNamespace) -> None:
    r = fx.client.post(
        "/v1/auth/token", json={"username": "demo.preparer", "password": "fixture-password-123"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["expires_in"] > 0


def test_NFR07_bad_password_is_401(fx: SimpleNamespace) -> None:
    r = fx.client.post(
        "/v1/auth/token", json={"username": "demo.preparer", "password": "wrong-password-000"}
    )
    _problem(r, 401, "UNAUTHENTICATED")


def test_NFR07_unknown_user_is_401_and_still_runs_one_password_verify(
    fx: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    import credassure.gateway.routers.auth as auth

    real = auth.verify_password
    calls: list[int] = []

    def counting(*args: Any, **kwargs: Any) -> Any:
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(auth, "verify_password", counting)
    r = fx.client.post(
        "/v1/auth/token", json={"username": "nobody.here", "password": "fixture-password-123"}
    )
    _problem(r, 401, "UNAUTHENTICATED")
    assert len(calls) == 1  # timing-equal: no username enumeration


def test_NFR07_me_returns_the_caller(fx: SimpleNamespace) -> None:
    r = fx.client.get("/v1/me", headers=fx.login("demo.director"))
    assert r.status_code == 200
    assert r.json() == {
        "user_id": "u-demo.director",
        "username": "demo.director",
        "role": "director_finance",
    }


def test_NFR07_user_deactivated_after_login_gets_401(fx: SimpleNamespace) -> None:
    h = fx.login("demo.preparer")
    with sqlite3.connect(fx.client.db) as con:
        con.execute("UPDATE users SET active=0 WHERE username='demo.preparer'")
    _problem(fx.client.get("/v1/me", headers=h), 401, "UNAUTHENTICATED")


# --- Cases (UI-01, SUP-08) ------------------------------------------------------------------------


def test_UI01_preparer_creates_case_with_indicative_amount_kept_apart(fx: SimpleNamespace) -> None:
    h = fx.login("demo.preparer")
    body = {
        "msme_name": "Demo Electronics Pvt Ltd",
        "order_ref": "PO-1",
        "order_value_paise": 3_20_00_000_00,
        "indicative_amount_paise": 2_00_00_000_00,
        "due_date": "2027-05-15",
    }
    r = fx.client.post("/v1/cases", json=body, headers=h)
    assert r.status_code == 201, r.text
    created = r.json()
    assert re.fullmatch(r"CA-\d{4}-\d{4}", created["case_id"])
    assert created["status"] == "CREATED"
    case = _case(fx.client, h, created["case_id"])
    assert case["indicative_amount"]["paise"] == 2_00_00_000_00
    funding = fx.client.get(f"/v1/cases/{created['case_id']}/funding", headers=h).json()
    assert funding["recommended_amount"] is None  # BR-01: request is never the loan amount


def test_UI01_director_cannot_create_case(fx: SimpleNamespace) -> None:
    r = fx.client.post(
        "/v1/cases",
        json={
            "msme_name": "X",
            "order_ref": "PO-2",
            "order_value_paise": 100,
            "indicative_amount_paise": 100,
            "due_date": "2027-05-15",
        },
        headers=fx.login("demo.director"),
    )
    _problem(r, 403, "FORBIDDEN")


def test_SUP08_case_list_shows_only_visible_cases(fx: SimpleNamespace) -> None:
    case_id = fx.new_case()

    def ids(user: str) -> list[str]:
        r = fx.client.get("/v1/cases", headers=fx.login(user))
        assert r.status_code == 200
        return [i["case_id"] for i in r.json()["items"]]

    assert case_id in ids("demo.preparer")
    assert case_id not in ids("demo.preparer2")


def test_SUP08_other_preparer_gets_404_not_403(fx: SimpleNamespace) -> None:
    case_id = fx.new_case()
    r = fx.client.get(f"/v1/cases/{case_id}", headers=fx.login("demo.preparer2"))
    _problem(r, 404, "NOT_FOUND")


def test_SUP08_evaluator_sees_any_case(fx: SimpleNamespace) -> None:
    case_id = fx.new_case()
    case = _case(fx.client, fx.login("demo.evaluator"), case_id)
    assert case["case_id"] == case_id


# --- Files (UI-02) --------------------------------------------------------------------------------


def test_UI02_valid_csv_upload_returns_sha256_and_rows(fx: SimpleNamespace) -> None:
    from pathlib import Path

    data = (
        Path(__file__).resolve().parents[3] / "data/frozen/v1/cases/CA-2026-0001/costs.csv"
    ).read_bytes()
    r = _csv_upload(fx.client, fx.login("demo.preparer"), fx.new_case(), "costs.csv", data)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kind"] == "costs"
    assert body["sha256"] == hashlib.sha256(data).hexdigest()
    assert body["rows"] == len(data.decode().strip().splitlines()) - 1


def test_UI02_upload_over_2mb_is_413(fx: SimpleNamespace) -> None:
    _problem(_s413(fx), 413, "PAYLOAD_TOO_LARGE")


def test_UI02_xlsx_upload_is_415(fx: SimpleNamespace) -> None:
    _problem(_s415(fx), 415, "UNSUPPORTED_MEDIA_TYPE")


def test_UI02_invalid_csv_value_names_field_row_and_reason(fx: SimpleNamespace) -> None:
    body = _problem(_s422(fx), 422, "VALIDATION_FAILED")
    err = body["errors"][0]
    assert err["field"] == "amount"
    assert err["row"] == 2
    assert err["reason"]


def test_SUP08_other_preparer_cannot_upload_to_case(fx: SimpleNamespace) -> None:
    r = _csv_upload(
        fx.client, fx.login("demo.preparer2"), fx.new_case(), "costs.csv", b"week,category,amount\n"
    )
    _problem(r, 404, "NOT_FOUND")


# --- Runs and jobs (SUP-01, SUP-03, scope #47) ----------------------------------------------------


def test_scope47_run_returns_202_job_resource(fx: SimpleNamespace) -> None:
    case_id = fx.new_case()
    fx.upload(case_id)
    r = fx.client.post(f"/v1/cases/{case_id}/run", headers=fx.login("demo.preparer"))
    assert r.status_code == 202, r.text
    job = r.json()
    assert job["case_id"] == case_id
    assert job["status_url"] == f"/v1/jobs/{job['job_id']}"
    assert job["events_url"] == f"/v1/jobs/{job['job_id']}/events"


def test_scope47_same_idempotency_key_returns_same_job(fx: SimpleNamespace) -> None:
    case_id = fx.new_case()
    h = {**fx.login("demo.preparer"), "Idempotency-Key": "run-once-1"}
    first = fx.client.post(f"/v1/cases/{case_id}/run", headers=h)
    second = fx.client.post(f"/v1/cases/{case_id}/run", headers=h)
    assert first.status_code == second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]


def test_SUP01_full_run_job_succeeds_awaiting_approval(fx: SimpleNamespace) -> None:
    case_id = fx.new_case()
    fx.upload(case_id)
    h = fx.login("demo.preparer")
    job = fx.client.post(f"/v1/cases/{case_id}/run", headers=h).json()
    r = fx.client.get(job["status_url"], headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "succeeded"
    assert r.json()["outcome"] == "AWAITING_APPROVAL"


def test_scope47_sse_stream_has_stage_events_and_ends_with_end(fx: SimpleNamespace) -> None:
    case_id = fx.new_case()
    h = fx.login("demo.preparer")
    job = fx.client.post(f"/v1/cases/{case_id}/run", headers=h).json()
    r = fx.client.get(job["events_url"], headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "event: stage" in r.text
    events = [line for line in r.text.splitlines() if line.startswith("event:")]
    assert events[-1] == "event: end"


def test_SUP03_proposal_step_on_fresh_case_pauses_upstream_not_go(fx: SimpleNamespace) -> None:
    case_id = fx.new_case()
    h = fx.login("demo.preparer")
    job = fx.client.post(f"/v1/cases/{case_id}/proposal", headers=h)
    assert job.status_code == 202, job.text
    assert fx.client.get(job.json()["status_url"], headers=h).json()["outcome"] == "PAUSED"
    lendwise = [s for s in _case(fx.client, h, case_id)["stages"] if s["stage"] == "lendwise"]
    codes = {b["code"] for s in lendwise for b in s["blockers"]}
    assert "SUP_UPSTREAM_NOT_GO" in codes


def test_SUP03_director_cannot_start_run(fx: SimpleNamespace) -> None:
    case_id = fx.new_case()
    r = fx.client.post(f"/v1/cases/{case_id}/run", headers=fx.login("demo.director"))
    assert r.status_code in (403, 404)
    _problem(r, r.status_code)


# --- Decisions (APR-04, APR-05) -------------------------------------------------------------------


def test_APR05_preparer_cannot_decide_own_case(fx: SimpleNamespace) -> None:
    case_id = fx.run_case()
    h = fx.login("demo.preparer")
    r = _decide(fx.client, h, case_id, "approve", _case(fx.client, h, case_id)["row_version"])
    _problem(r, 403, "FORBIDDEN")


def test_APR02_vp_cannot_decide_director_routed_case(fx: SimpleNamespace) -> None:
    case_id = fx.run_case()
    version = _case(fx.client, fx.login("demo.evaluator"), case_id)["row_version"]
    r = _decide(fx.client, fx.login("demo.vp"), case_id, "approve", version)
    assert r.status_code in (403, 404)
    _problem(r, r.status_code)


def test_APR05_evaluator_cannot_decide(fx: SimpleNamespace) -> None:
    case_id = fx.run_case()
    h = fx.login("demo.evaluator")
    r = _decide(fx.client, h, case_id, "approve", _case(fx.client, h, case_id)["row_version"])
    _problem(r, 403, "FORBIDDEN")


def test_APR04_stale_expected_version_is_409(fx: SimpleNamespace) -> None:
    _problem(_s409(fx), 409, "CONFLICT")


def test_APR04_director_approves_routed_case(fx: SimpleNamespace) -> None:
    case_id = fx.run_case()
    h = fx.login("demo.director")
    case = _case(fx.client, h, case_id)
    assert case["route"] == "director_finance"
    r = _decide(fx.client, h, case_id, "approve", case["row_version"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APPROVED"
    assert r.json()["approval_id"]


def test_APR05_return_reopens_only_the_named_stage(fx: SimpleNamespace) -> None:
    case_id = fx.run_case()
    d, p = fx.login("demo.director"), fx.login("demo.preparer")
    version = _case(fx.client, d, case_id)["row_version"]
    r = _decide(fx.client, d, case_id, "return", version, return_stage="working_capital")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "RETURNED"
    assert _case(fx.client, p, case_id)["current_stage"] == "working_capital"

    job = fx.client.post(f"/v1/cases/{case_id}/run", headers=p).json()
    assert fx.client.get(job["status_url"], headers=p).json()["outcome"] == "AWAITING_APPROVAL"
    attempts = _attempts(_case(fx.client, p, case_id))
    assert attempts["onboarding"] == 1
    assert attempts["working_capital"] == 2


def test_S1_return_with_no_pending_approval_is_409_and_fails_closed(fx: SimpleNamespace) -> None:
    """Ledger says AWAITING_APPROVAL but the graph never reached the interrupt (lost checkpoint)."""
    from credassure.ledger import reads
    from credassure.ledger.session import transaction

    case_id = fx.new_case()
    svc = fx.client.app.state.services
    svc.ledger.route(case_id, "director_finance")  # no graph run: nothing pending
    d = fx.login("demo.director")
    version = _case(fx.client, d, case_id)["row_version"]
    r = _decide(fx.client, d, case_id, "return", version, return_stage="working_capital")
    _problem(r, 409, "CONFLICT")
    case = _case(fx.client, fx.login("demo.preparer"), case_id)
    assert case["status"] == "FAILED"
    with transaction(svc.engine) as s:
        assert reads.approvals(s, svc.settings.tenant_id, case_id) == []  # not recorded as applied
    assert any(
        b["code"] == "SUP_RETURN_NO_PENDING_APPROVAL"
        for st in case["stages"]
        for b in st.get("blockers", [])
    )


# --- Inbox (UI-07) --------------------------------------------------------------------------------


def test_UI07_director_inbox_lists_routed_case(fx: SimpleNamespace) -> None:
    case_id = fx.run_case()
    r = fx.client.get("/v1/inbox", headers=fx.login("demo.director"))
    assert r.status_code == 200
    assert case_id in [i["case_id"] for i in r.json()["items"]]


def test_UI07_preparer_has_no_inbox(fx: SimpleNamespace) -> None:
    _problem(fx.client.get("/v1/inbox", headers=fx.login("demo.preparer")), 403, "FORBIDDEN")


# --- Funding, offers, chat, report, audit, admin, eval -------------------------------------------


def test_UI04_funding_shows_recommended_amount_after_run(fx: SimpleNamespace) -> None:
    case_id = fx.run_case()
    r = fx.client.get(f"/v1/cases/{case_id}/funding", headers=fx.login("demo.preparer"))
    assert r.status_code == 200
    rec = r.json()["recommended_amount"]
    assert rec["paise"] == 1_42_00_000_00  # placeholder WC: ₹1,42,00,000 (spec)
    assert "1,42,00,000" in rec["display"]


def test_UI05_offers_route_returns_offers_and_facts(fx: SimpleNamespace) -> None:
    case_id = fx.run_case()
    r = fx.client.get(f"/v1/cases/{case_id}/offers", headers=fx.login("demo.preparer"))
    assert r.status_code == 200
    assert {"gate", "source", "ranking", "offers"} <= r.json().keys()
    assert r.json()["gate"] == "GO" and r.json()["source"] == "ledger"


def test_UI06_CP02_chat_with_llm_off_abstains(fx: SimpleNamespace) -> None:
    case_id = fx.new_case()
    r = fx.client.post(
        f"/v1/cases/{case_id}/chat",
        json={"message": "What is a KFS?"},
        headers=fx.login("demo.preparer"),
    )
    assert r.status_code == 200, r.text
    assert r.json()["answer"] == "I can't verify that from the available sources."  # model off


def test_UI08_report_has_every_trace_id_and_internal_approval_wording(
    fx: SimpleNamespace,
) -> None:
    case_id = fx.run_case()
    h = fx.login("demo.preparer")
    trace_ids = [s["trace_id"] for s in _case(fx.client, h, case_id)["stages"]]
    assert trace_ids
    r = fx.client.get(f"/v1/cases/{case_id}/report", params={"fmt": "md"}, headers=h)
    assert r.status_code == 200
    assert all(t in r.text for t in trace_ids)
    assert "not loan acceptance" in r.text  # APR-06


def test_OBJ08_evaluator_audit_chain_verifies(fx: SimpleNamespace) -> None:
    case_id = fx.run_case()
    r = fx.client.get(f"/v1/cases/{case_id}/audit", headers=fx.login("demo.evaluator"))
    assert r.status_code == 200
    assert r.json()["chain_ok"] is True
    assert r.json()["events"]


def test_OBJ08_preparer_cannot_read_audit(fx: SimpleNamespace) -> None:
    case_id = fx.new_case()
    r = fx.client.get(f"/v1/cases/{case_id}/audit", headers=fx.login("demo.preparer"))
    _problem(r, 403, "FORBIDDEN")


def test_APR03_evaluator_sets_boundary_rule(fx: SimpleNamespace) -> None:
    r = fx.client.post(
        "/v1/admin/config",
        json={"key": "boundary_rule", "value": "vp"},
        headers=fx.login("demo.evaluator"),
    )
    assert r.status_code == 200, r.text


def test_APR03_preparer_cannot_set_config(fx: SimpleNamespace) -> None:
    r = fx.client.post(
        "/v1/admin/config",
        json={"key": "boundary_rule", "value": "vp"},
        headers=fx.login("demo.preparer"),
    )
    _problem(r, 403, "FORBIDDEN")


def test_API01_eval_runs_not_implemented_for_evaluator(fx: SimpleNamespace) -> None:
    h = fx.login("demo.evaluator")
    _problem(fx.client.post("/v1/eval/runs", json={}, headers=h), 501, "NOT_IMPLEMENTED")
    _problem(fx.client.get("/v1/eval/runs/x", headers=h), 501, "NOT_IMPLEMENTED")


def test_API01_eval_runs_forbidden_for_preparer(fx: SimpleNamespace) -> None:
    r = fx.client.post("/v1/eval/runs", json={}, headers=fx.login("demo.preparer"))
    _problem(r, 403, "FORBIDDEN")


# --- Health and quota (scope #16, #50, NFR-03) ----------------------------------------------------


def test_scope50_live_needs_no_auth(fx: SimpleNamespace) -> None:
    r = fx.client.get("/v1/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.parametrize(("llm_enabled", "model"), [(False, "disabled"), (True, "closed")])
def test_scope50_ready_reports_checks(fx: SimpleNamespace, llm_enabled: bool, model: str) -> None:
    c = fx.make_client(llm_enabled=llm_enabled)
    r = c.get("/v1/health/ready")
    assert r.status_code == 200
    checks = r.json()["checks"]
    assert set(checks) == {"db", "chroma", "model", "quota"}
    assert checks["db"] == "ok"
    assert checks["chroma"] == "not_configured"
    assert checks["model"] == model
    assert checks["quota"]["level"] == "ok"


def _spend(db: Any, case_id: str, tokens: int) -> None:
    with sqlite3.connect(db) as con:
        con.execute(
            "INSERT INTO stage_runs (tenant_id, case_id, stage, attempt, decision, result_json,"
            " trace_id, started_at) VALUES ('default', ?, 'onboarding', 99, 'GO', ?, 'tr-q',"
            " '2026-11-07 00:00:00')",
            (case_id, f'{{"tokens_used": {tokens}}}'),
        )


def test_scope16_quota_levels_and_run_warning_header(fx: SimpleNamespace) -> None:
    c = fx.make_client(token_quota=1000)
    h = fx.login("demo.preparer", c)
    spent_on, run_on = fx.new_case(c), fx.new_case(c)

    def quota() -> dict[str, Any]:
        q: dict[str, Any] = c.get("/v1/health/ready").json()["checks"]["quota"]
        return q

    _spend(c.db, spent_on, 700)  # 70 % of 1000
    assert quota() == {"used": 700, "limit": 1000, "level": "warn_70"}
    assert c.post(f"/v1/cases/{run_on}/run", headers=h).headers["X-Quota-Warning"] == "warn_70"

    _spend(c.db, spent_on, 200)  # 90 %
    assert quota()["level"] == "warn_90"
    run_on2 = fx.new_case(c)
    r = c.post(f"/v1/cases/{run_on2}/run", headers=h)
    assert r.status_code == 202
    assert r.headers["X-Quota-Warning"] == "warn_90"


# --- Rate limit (NFR-04) --------------------------------------------------------------------------


def test_NFR04_over_rate_limit_is_429(fx: SimpleNamespace) -> None:
    c = fx.make_client(rate_limit="3/minute")
    h = fx.login("demo.preparer", c)
    responses = [c.get("/v1/me", headers=h) for _ in range(4)]
    assert responses[0].status_code == 200
    _problem(responses[-1], 429, "RATE_LIMITED")
