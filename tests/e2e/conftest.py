"""E2E fixtures (scope #15). Duplicated minimal versions of apps/gateway/tests/conftest.py, since
importlib mode cannot share conftest helpers across directories. No network, FakeLLM only."""

from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from credassure.llm.fake import FakeLLM

PASSWORD = "fixture-password-123"


@pytest.fixture
def make_client(tmp_path: Path) -> Iterator[Callable[[bool], tuple[TestClient, FakeLLM | None]]]:
    stack = ExitStack()

    def _make(llm_enabled: bool) -> tuple[TestClient, FakeLLM | None]:
        from credassure.gateway.main import create_app
        from credassure.gateway.settings import Settings
        from credassure.ledger.seed import seed

        db = tmp_path / "case.db"
        seed(db, {"SEED_PASSWORD": PASSWORD})
        settings: Any = Settings(
            _env_file=None,  # type: ignore[call-arg]
            app_env="test",
            jwt_secret="x" * 40,
            case_db=db,
            llm_enabled=llm_enabled,
            tracing_enabled=False,
        )
        llm = FakeLLM() if llm_enabled else None
        app = create_app(settings, llm=llm) if llm is not None else create_app(settings)
        return stack.enter_context(TestClient(app)), llm

    yield _make
    stack.close()


@pytest.fixture
def login() -> Callable[[TestClient, str], dict[str, str]]:
    def _login(client: TestClient, username: str) -> dict[str, str]:
        r = client.post("/v1/auth/token", json={"username": username, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login
