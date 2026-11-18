"""Observability gaps (ARCHITECTURE §8.8): request id in every problem, metrics, client errors."""

import json
import logging
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from credassure.gateway.metrics import MeteredLLM, Metrics
from credassure.llm.fake import FakeLLM

Login = Callable[[TestClient, str], dict[str, str]]
PAN = "ABCPE1234F"


def test_problem_body_carries_the_request_id_of_its_header(client: TestClient) -> None:
    r = client.get("/v1/cases/CA-0000-0000")  # no token
    body = r.json()
    assert r.status_code == 401 and body["request_id"] == r.headers["X-Request-ID"]


def test_unhandled_error_is_500_with_request_id_logged_and_counted(
    client: Any, login: Login, caplog: pytest.LogCaptureFixture
) -> None:
    def boom() -> None:
        raise RuntimeError(f"boom {PAN}")

    client.app.add_api_route("/v1/__crash", boom)
    raw = TestClient(client.app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="credassure.problems"):
        r = raw.get("/v1/__crash")
    assert r.status_code == 500
    rid = r.json()["request_id"]
    assert r.headers["X-Request-ID"] == rid and "boom" not in r.text  # no detail leaks
    assert client.app.state.metrics.unhandled == 1
    text = client.get("/v1/metrics", headers=login(client, "demo.evaluator")).text
    assert "credassure_unhandled_errors_total 1" in text


def test_metrics_are_evaluator_only_and_use_route_templates(
    client: TestClient, login: Login
) -> None:
    prep = login(client, "demo.preparer")
    client.get("/v1/cases/CA-2099-0001", headers=prep)
    assert client.get("/v1/metrics", headers=prep).status_code == 403
    r = client.get("/v1/metrics", headers=login(client, "demo.evaluator"))
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/plain")
    assert 'route="/v1/cases/{case_id}"' in r.text  # template, never the raw case id
    assert "CA-2099-0001" not in r.text
    assert 'credassure_http_request_duration_seconds_bucket{method="GET"' in r.text


def test_client_error_is_redacted_logged_counted_and_needs_login(
    client: TestClient, login: Login, caplog: pytest.LogCaptureFixture
) -> None:
    report = {
        "kind": "render",
        "message": f"TypeError for {PAN}",
        "page": f"/case/?id=CA-1&pan={PAN}",
        "stack": f"at x ({PAN})",
        "request_id": "a" * 32,
    }
    assert client.post("/v1/client-errors", json=report).status_code == 401
    with caplog.at_level(logging.ERROR, logger="credassure.client"):
        r = client.post("/v1/client-errors", json=report, headers=login(client, "demo.preparer"))
    assert r.status_code == 204
    rec = next(x for x in caplog.records if x.name == "credassure.client")
    logged = json.dumps({k: str(v) for k, v in vars(rec).items()})
    assert PAN not in logged and rec.page == "/case/"  # query string dropped
    assert rec.client_request_id == "a" * 32
    assert client.app.state.metrics.client_errors["render"] == 1


def test_client_error_report_size_is_capped(client: TestClient, login: Login) -> None:
    big = {"kind": "error", "message": "x" * 501}
    r = client.post("/v1/client-errors", json=big, headers=login(client, "demo.preparer"))
    assert r.status_code == 422


def test_metered_llm_counts_outcomes_and_delegates() -> None:
    m = Metrics()
    fake = FakeLLM()
    llm = MeteredLLM(fake, m)
    llm.complete("hello", name="cp_answer")
    assert m.llm_calls[("cp_answer", "ok")] == 1
    assert llm.__getattr__("complete")  # delegation of anything else
    assert 'credassure_llm_calls_total{prompt="cp_answer",outcome="ok"} 1' in m.render()
