"""E2E fixtures (scope #15). Duplicated minimal versions of apps/gateway/tests/conftest.py, since
importlib mode cannot share conftest helpers across directories. No network, FakeLLM only."""

import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from credassure.llm.fake import FakeLLM

PASSWORD = "fixture-password-123"


@pytest.fixture
def make_client(tmp_path: Path) -> Iterator[Callable[..., tuple[TestClient, FakeLLM | None]]]:
    stack = ExitStack()

    def _make(llm_enabled: bool, **overrides: Any) -> tuple[TestClient, FakeLLM | None]:
        from credassure.gateway.main import create_app
        from credassure.gateway.settings import Settings
        from credassure.ledger import testing
        from credassure.ledger.seed import seed

        db = tmp_path / "case.db"
        if (url := testing.mysql_url()) is not None:  # ADR 0039: a fresh MySQL database
            mysql = testing.create_database(url, "e2e")
            stack.callback(testing.drop_database, mysql)
            overrides.setdefault("case_database_url", mysql)
            overrides.setdefault("checkpoint_db", tmp_path / "checkpoints.db")
            seed(mysql, {"SEED_PASSWORD": PASSWORD})
        else:
            seed(db, {"SEED_PASSWORD": PASSWORD})
        settings: Any = Settings(
            _env_file=None,
            app_env="test",
            jwt_secret="x" * 40,
            case_db=db,
            llm_enabled=llm_enabled,
            tracing_enabled=False,
            **overrides,
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


@pytest.fixture
def upload_offers() -> Callable[[TestClient, str, dict[str, str]], None]:
    """The demo case's v1 offers with their KFS and schedules of charges (LW-01, LW-04)."""
    frozen = Path(__file__).resolve().parents[2] / "data" / "frozen" / "v1"

    def _upload(client: TestClient, case_id: str, headers: dict[str, str]) -> None:
        for offer in sorted((frozen / "offers" / "CA-2026-0001").glob("*.v1.json")):
            doc = json.loads(offer.read_text())["kfs_doc_id"]
            for kind, path in (
                ("offer", offer),
                ("kfs", frozen / "kfs" / f"{doc}.md"),
                ("kfs", frozen / "kfs" / f"{doc}-SCH.md"),
            ):
                mime = "application/json" if kind == "offer" else "text/markdown"
                r = client.post(
                    f"/v1/cases/{case_id}/files",
                    params={"kind": kind},
                    files={"file": (path.name, path.read_bytes(), mime)},
                    headers=headers,
                )
                assert r.status_code == 201, (kind, r.text)

    return _upload
