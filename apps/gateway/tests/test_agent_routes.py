"""Agent routers are mounted and fail closed until their phase (ADR 0005, scope #28)."""

from fastapi.testclient import TestClient

from credassure.gateway.main import create_app
from credassure.gateway.settings import Settings


def client() -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, app_env="test")))


def test_health_live_still_ok() -> None:
    response = client().get("/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_agent_card() -> None:
    response = client().get("/v1/agents/lendwise/card")
    assert response.status_code == 200
    assert response.json()["name"] == "lendwise"


def test_stage_run_returns_501() -> None:
    response = client().post("/v1/agents/onboarding/cases/CA-2026-0001/run")
    assert response.status_code == 501
    assert "not implemented" in response.json()["detail"]


def test_copilot_chat_returns_501() -> None:
    response = client().post("/v1/agents/copilot/cases/CA-2026-0001/chat")
    assert response.status_code == 501
    assert "not implemented" in response.json()["detail"]
