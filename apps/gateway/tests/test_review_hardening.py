"""Phase 8b review fixes (security-reviewer S3-S9, N1-N3, N7; brd-conformance SHOULDs).

Uploads fail closed on hostile input, logins are throttled per user, chat never returns
unverified model text, the report is escaped and locked down, and every 500 has its own code.
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from credassure.ledger.session import run_lock

RECEIVABLES = "invoice_id,customer,amount,due_week,expected_week\n"


def _upload(c: TestClient, h: dict[str, str], case_id: str, kind: str, name: str, data: bytes,
            mime: str = "text/csv") -> Any:  # fmt: skip
    return c.post(
        f"/v1/cases/{case_id}/files",
        params={"kind": kind},
        files={"file": (name, data, mime)},
        headers=h,
    )


@pytest.fixture
def prep(
    client: Any,
    login: Callable[[TestClient, str], dict[str, str]],
    new_case: Callable[[TestClient], str],
) -> tuple[Any, dict[str, str], str]:
    return client, login(client, "demo.preparer"), new_case(client)


def _code(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["code"] == code


# --- uploads -----


def test_S10_upload_while_a_run_holds_the_lock_is_409(prep: Any) -> None:
    c, h, case_id = prep
    svc = c.app.state.services
    with run_lock(svc.engine, svc.settings.tenant_id, case_id, "job-x"):
        r = _upload(
            c, h, case_id, "receivables", "r.csv", (RECEIVABLES + "I1,A,100,3,3\n").encode()
        )
    _code(r, 409, "RUN_IN_PROGRESS")


@pytest.mark.parametrize("cell", ['=HYPERLINK("x")', "+cmd", "-2+3", "@SUM(A1)"])
def test_S7_csv_formula_in_a_text_cell_is_422(prep: Any, cell: str) -> None:
    c, h, case_id = prep
    data = (RECEIVABLES + f"I1,{cell},100,3,3\n").encode()
    r = _upload(c, h, case_id, "receivables", "r.csv", data)
    _code(r, 422, "VALIDATION_FAILED")
    assert r.json()["errors"][0]["field"] == "customer"


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "1e30", "-1e30"])
def test_S8_non_finite_or_out_of_range_money_is_422(prep: Any, amount: str) -> None:
    c, h, case_id = prep
    data = (RECEIVABLES + f"I1,Acme,{amount},3,3\n").encode()
    _code(_upload(c, h, case_id, "receivables", "r.csv", data), 422, "VALIDATION_FAILED")


def test_N3_csv_parser_error_is_422(prep: Any) -> None:
    c, h, case_id = prep
    data = (RECEIVABLES + "I1," + "x" * 200_000 + ",100,3,3\n").encode()  # > csv field limit
    _code(_upload(c, h, case_id, "receivables", "r.csv", data), 422, "VALIDATION_FAILED")


def test_N3_deeply_nested_json_is_422(prep: Any) -> None:
    c, h, case_id = prep
    data = ("[" * 100_000 + "]" * 100_000).encode()
    r = _upload(c, h, case_id, "order", "o.json", data, mime="application/json")
    _code(r, 422, "VALIDATION_FAILED")


# --- login throttle (S4) -----


def test_S4_sixth_failed_login_for_one_user_in_a_minute_is_429(client: Any) -> None:
    body = {"username": "demo.director", "password": "wrong-password"}
    codes = [client.post("/v1/auth/token", json=body).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429


# --- chat (S9 / BRD: no unverified model text) -----


def test_S9_chat_with_llm_on_never_returns_raw_model_text(
    make_client: Callable[..., Any],
    login: Callable[[TestClient, str], dict[str, str]],
    new_case: Callable[[TestClient], str],
) -> None:
    c = make_client(llm_enabled=True, copilot_search_mode="keyword")
    case_id = new_case(c)
    r = c.post(
        f"/v1/cases/{case_id}/chat",
        json={"message": "What is a KFS?"},
        headers=login(c, "demo.preparer"),
    )
    assert r.status_code == 200, r.text
    assert {"answer", "citations", "intent", "trace_id"} <= r.json().keys()
    # FakeLLM's default "ok" is not valid output: it never reaches the user (CP-02)
    assert r.json()["answer"] == "I can't verify that from the available sources."
    assert any(name == "cp_answer" or name == "cp_tool" for name, _ in c.llm.calls)


# --- report (S6, N7) -----


def test_S6_report_escapes_markdown_and_html_has_security_headers(
    client: Any, login: Callable[[TestClient, str], dict[str, str]]
) -> None:
    h = login(client, "demo.preparer")
    body = {
        "msme_name": "Evil](http://x) <script>alert(1)</script>",
        "order_ref": "PO-1",
        "order_value_paise": 100,
        "indicative_amount_paise": 100,
        "due_date": "2027-05-15",
    }
    case_id = client.post("/v1/cases", json=body, headers=h).json()["case_id"]
    md = client.get(f"/v1/cases/{case_id}/report", params={"fmt": "md"}, headers=h)
    assert "](http://x)" not in md.text
    page = client.get(f"/v1/cases/{case_id}/report", params={"fmt": "html"}, headers=h)
    assert "<script>" not in page.text
    assert page.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in page.headers["content-security-policy"]


# --- problems and middleware (N1, N2) -----


def test_N1_unhandled_error_is_500_with_INTERNAL_ERROR(client: Any) -> None:
    def boom() -> None:
        raise RuntimeError("secret detail")

    client.app.add_api_route("/v1/boom", boom)
    c = TestClient(client.app, raise_server_exceptions=False)
    r = c.get("/v1/boom")
    _code(r, 500, "INTERNAL_ERROR")
    assert "secret detail" not in r.text


def test_N2_cors_headers_present_even_on_a_429(make_client: Callable[..., Any]) -> None:
    c = make_client(rate_limit="1/minute", ui_origins="http://ui.test")
    origin = {"Origin": "http://ui.test"}
    c.get("/v1/me", headers=origin)
    r = c.get("/v1/me", headers=origin)
    assert r.status_code == 429
    assert r.headers.get("access-control-allow-origin") == "http://ui.test"


def test_S5_sse_ends_stale_when_a_running_job_has_no_live_run(
    prep: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from credassure.gateway.routers import workflow

    c, h, case_id = prep
    svc = c.app.state.services
    job = svc.ledger.create_job(case_id, kind="run", stage=None, idempotency_key=None, actor="t")
    assert svc.ledger.claim_job(job.id)  # running, but no run lock: the worker died
    monkeypatch.setattr(workflow, "SSE_DEAD_GRACE", 0.0)
    monkeypatch.setattr(workflow, "SSE_POLL_SECONDS", 0.01)
    r = c.get(f"/v1/jobs/{job.id}/events", headers=h)
    assert r.status_code == 200
    assert 'event: end\ndata: {"status": "stale"' in r.text


def test_scope47_run_while_another_run_holds_the_lock_is_409(prep: Any) -> None:
    c, h, case_id = prep
    svc = c.app.state.services
    with run_lock(svc.engine, svc.settings.tenant_id, case_id, "job-x"):
        r = c.post(f"/v1/cases/{case_id}/run", headers=h)
    _code(r, 409, "RUN_IN_PROGRESS")
