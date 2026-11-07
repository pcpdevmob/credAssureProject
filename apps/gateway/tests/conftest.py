"""Gateway test fixtures (Phase 8b, docs/build/phase8-api-spec.md "App factory and fixtures").

Each client gets its own tmp case.db seeded with the S08 demo users. No network, no model: with
the LLM on the app gets a FakeLLM. Fixtures return callables because importlib mode forbids
importing helpers from this file (API-01: tests drive the same HTTP endpoints a UI would).
"""

import shutil
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from credassure.llm.fake import FakeLLM

PASSWORD = "fixture-password-123"
DEMO_CASE = (
    Path(__file__).resolve().parents[3] / "data" / "frozen" / "v1" / "cases" / "CA-2026-0001"
)
FILE_KINDS = (
    "order",
    "opening_position",
    "costs",
    "receipts",
    "receivables",
    "payables",
    "inventory",
)
NEW_CASE = {
    "msme_name": "Demo Electronics Pvt Ltd",
    "order_ref": "PO-CA-2026-0001",
    "order_value_paise": 3_20_00_000_00,
    "indicative_amount_paise": 2_00_00_000_00,
    "due_date": "2027-05-15",
}


class GatewayClient(TestClient):
    """TestClient that also exposes the FakeLLM (None when the LLM is off) and the case.db path."""

    llm: FakeLLM | None
    db: Path


@pytest.fixture(scope="session")
def seeded_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Seed once (25 argon2 hashes are slow); each client copies this file."""
    from credassure.ledger.seed import seed

    db = tmp_path_factory.mktemp("template") / "case.db"
    seed(db, {"SEED_PASSWORD": PASSWORD})
    return db


@pytest.fixture
def make_client(tmp_path: Path, seeded_template: Path) -> Iterator[Callable[..., GatewayClient]]:
    stack = ExitStack()
    count = 0

    def _make(llm_enabled: bool = False, **overrides: Any) -> GatewayClient:
        nonlocal count
        from credassure.gateway.main import create_app
        from credassure.gateway.settings import Settings

        count += 1
        db = tmp_path / f"case-{count}.db"
        shutil.copyfile(seeded_template, db)
        settings = Settings(
            _env_file=None,  # type: ignore[call-arg]
            app_env="test",
            jwt_secret="x" * 40,
            case_db=db,
            llm_enabled=llm_enabled,
            tracing_enabled=False,
            **overrides,
        )
        llm = FakeLLM() if llm_enabled else None
        app = create_app(settings, llm=llm) if llm is not None else create_app(settings)
        client = stack.enter_context(GatewayClient(app))
        client.llm, client.db = llm, db
        return client

    yield _make
    stack.close()


@pytest.fixture
def client(make_client: Callable[..., GatewayClient]) -> GatewayClient:
    """Default client: LLM off, default settings."""
    return make_client(llm_enabled=False)


@pytest.fixture
def login() -> Callable[[TestClient, str], dict[str, str]]:
    def _login(client: TestClient, username: str) -> dict[str, str]:
        r = client.post("/v1/auth/token", json={"username": username, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _login


@pytest.fixture
def new_case(
    login: Callable[[TestClient, str], dict[str, str]],
) -> Callable[[TestClient], str]:
    def _new(client: TestClient) -> str:
        r = client.post("/v1/cases", json=NEW_CASE, headers=login(client, "demo.preparer"))
        assert r.status_code == 201, r.text
        return str(r.json()["case_id"])

    return _new


@pytest.fixture
def upload_demo_files(
    login: Callable[[TestClient, str], dict[str, str]],
) -> Callable[[TestClient, str], None]:
    def _upload(client: TestClient, case_id: str) -> None:
        headers = login(client, "demo.preparer")
        for kind in FILE_KINDS:
            name = f"{kind}.json" if kind in ("order", "opening_position") else f"{kind}.csv"
            mime = "application/json" if name.endswith(".json") else "text/csv"
            r = client.post(
                f"/v1/cases/{case_id}/files",
                params={"kind": kind},
                files={"file": (name, (DEMO_CASE / name).read_bytes(), mime)},
                headers=headers,
            )
            assert r.status_code == 201, (kind, r.text)

    return _upload


@pytest.fixture
def run_case(
    login: Callable[[TestClient, str], dict[str, str]],
    new_case: Callable[[TestClient], str],
    upload_demo_files: Callable[[TestClient, str], None],
) -> Callable[[TestClient], str]:
    """Create the demo case, upload its 7 files and run it to AWAITING_APPROVAL (director route)."""

    def _run(client: TestClient) -> str:
        case_id = new_case(client)
        upload_demo_files(client, case_id)
        r = client.post(f"/v1/cases/{case_id}/run", headers=login(client, "demo.preparer"))
        assert r.status_code == 202, r.text
        return case_id

    return _run
