"""Smoke test: the gateway starts and answers its liveness probe."""

from fastapi.testclient import TestClient

from credassure.gateway.main import create_app
from credassure.gateway.settings import Settings


def test_health_live_returns_ok() -> None:
    app = create_app(Settings(_env_file=None, app_env="test"))
    response = TestClient(app).get("/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]
