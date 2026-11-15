"""Agent routers under /v1/agents/<name> (ADR 0005, scope #28, phase8-api-spec.md "Agent routers").

Stage runs go through the Supervisor (SUP-01, SUP-03); case routes need gateway auth (NFR-07).
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

AGENTS = ("supervisor", "onboarding", "working-capital", "lendwise", "critic", "copilot")
STAGE_AGENTS = {
    "onboarding": "onboarding",
    "working-capital": "working_capital",
    "lendwise": "lendwise",
    "critic": "critic",
}
Login = Callable[[TestClient, str], dict[str, str]]


def _problem(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == code


@pytest.mark.parametrize("name", AGENTS)
def test_scope28_agent_card_is_public(client: TestClient, name: str) -> None:
    r = client.get(f"/v1/agents/{name}/card")
    assert r.status_code == 200
    assert r.json()["name"] == name.replace("-", "_")
    assert r.json()["version"]


@pytest.mark.parametrize("name", AGENTS)
def test_scope28_agent_health_is_public(client: TestClient, name: str) -> None:
    assert client.get(f"/v1/agents/{name}/health").status_code == 200


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/v1/agents/onboarding/cases/CA-2026-0001/run"),
        ("get", "/v1/agents/lendwise/cases/CA-2026-0001/result"),
        ("get", "/v1/agents/supervisor/cases/CA-2026-0001/plan"),
        ("post", "/v1/agents/copilot/cases/CA-2026-0001/chat"),
    ],
)
def test_NFR07_agent_case_routes_need_auth(client: TestClient, method: str, path: str) -> None:
    _problem(getattr(client, method)(path), 401, "UNAUTHENTICATED")


@pytest.mark.parametrize(("name", "stage"), STAGE_AGENTS.items())
def test_SUP03_agent_run_starts_a_job_for_that_stage_only(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str], name: str, stage: str
) -> None:
    case_id = new_case(client)
    h = login(client, "demo.preparer")
    r = client.post(f"/v1/agents/{name}/cases/{case_id}/run", headers=h)
    assert r.status_code == 202, r.text
    job = client.get(r.json()["status_url"], headers=h).json()
    assert job["stage"] == stage
    ran = {s["stage"] for s in client.get(f"/v1/cases/{case_id}", headers=h).json()["stages"]}
    assert ran <= {stage}


def test_SUP01_onboarding_run_on_fresh_case_is_go(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    h = login(client, "demo.preparer")
    r = client.post(f"/v1/agents/onboarding/cases/{case_id}/run", headers=h)
    assert client.get(r.json()["status_url"], headers=h).json()["status"] == "succeeded"
    result = client.get(f"/v1/agents/onboarding/cases/{case_id}/result", headers=h)
    assert result.status_code == 200
    assert result.json()["decision"] == "GO"
    assert result.json()["case_id"] == case_id


def test_scope28_result_is_404_before_any_run(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    r = client.get(
        f"/v1/agents/onboarding/cases/{case_id}/result", headers=login(client, "demo.preparer")
    )
    _problem(r, 404, "NOT_FOUND")


def test_scope19_supervisor_plan_lists_the_four_stages(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    r = client.get(
        f"/v1/agents/supervisor/cases/{case_id}/plan", headers=login(client, "demo.preparer")
    )
    assert r.status_code == 200
    assert r.json()["stages"] == ["onboarding", "working_capital", "lendwise", "critic"]


def test_scope25_retry_is_501(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    """Negotiation (LW-12) is built in 9c-b (test_lw_items.py); stage retry is still to come."""
    case_id = new_case(client)
    path = f"/v1/agents/supervisor/cases/{case_id}/stages/onboarding/retry"
    _problem(client.post(path, headers=login(client, "demo.evaluator")), 501, "NOT_IMPLEMENTED")


def test_scope25_retry_is_evaluator_only(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    path = f"/v1/agents/supervisor/cases/{case_id}/stages/onboarding/retry"
    _problem(client.post(path, headers=login(client, "demo.preparer")), 403, "FORBIDDEN")


def test_UI06_copilot_router_chat_matches_core_chat(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    r = client.post(
        f"/v1/agents/copilot/cases/{case_id}/chat",
        json={"message": "What is a KFS?"},
        headers=login(client, "demo.preparer"),
    )
    assert r.status_code == 200, r.text
    assert {"answer", "citations", "intent", "trace_id"} <= r.json().keys()
    assert "unavailable" in r.json()["answer"].lower()  # client fixture has the LLM off
