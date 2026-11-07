"""Smoke test: the gateway starts and answers its liveness probe (scope #50)."""

from pathlib import Path

from fastapi.testclient import TestClient

from credassure.gateway.main import create_app
from credassure.gateway.settings import Settings


def test_health_live_returns_ok(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        case_db=tmp_path / "case.db",  # never the developer's var/case.db
        llm_enabled=False,
        tracing_enabled=False,
    )
    response = TestClient(create_app(settings)).get("/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]
