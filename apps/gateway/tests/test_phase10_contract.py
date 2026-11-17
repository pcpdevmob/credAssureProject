"""Scope #51 + contract tests (ADR 0004, E10 SHOULD-1/2): openapi.json declares bearer security and
problem+json errors; every protected route refuses an anonymous caller with a 401 problem; an
oversized upload is refused before multipart parsing; Schemathesis fuzzes the whole schema."""

import shutil
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import schemathesis
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, settings

from credassure.gateway.main import create_app
from credassure.gateway.settings import Settings

PASSWORD = "fixture-password-123"  # conftest.PASSWORD
PUBLIC = {
    ("/v1/auth/token", "post"),
    ("/v1/health/live", "get"),
    ("/v1/health/ready", "get"),
}
SAMPLE = {
    "case_id": "CA-2026-0001",
    "stage": "onboarding",
    "key": "wc.gate",
    "chunk_id": "x",
    "job_id": "x",
    "run_id": "x",
}
METHODS = {"get", "post", "delete", "put", "patch"}


def _public(path: str, method: str) -> bool:
    return (path, method) in PUBLIC or path.endswith(("/card", "/health"))


def _ops(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (path, method, op)
        for path, item in schema["paths"].items()
        for method, op in item.items()
        if method in METHODS
    ]


def test_scope51_E10S2_protected_operations_declare_bearer_security(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    missing = [(p, m) for p, m, op in _ops(schema) if not _public(p, m) and not op.get("security")]
    assert missing == []


def test_scope51_E10S2_errors_are_declared_as_problem_json(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    problem = schema["components"]["schemas"]["Problem"]
    assert {"type", "title", "status", "detail", "code"} <= set(problem["required"])
    for path, method, op in _ops(schema):
        r = op["responses"]
        assert "application/problem+json" in r["4XX"]["content"], (path, method)
        if "422" in r:
            assert set(r["422"]["content"]) == {"application/problem+json"}, (path, method)


def _url(path: str) -> str:
    for name, value in SAMPLE.items():
        path = path.replace(f"{{{name}}}", value)
    return path


def test_API01_every_protected_route_refuses_anonymous_with_401_problem(
    client: TestClient,
) -> None:
    """A contract test per route: same request a UI would send, minus the token."""
    schema = client.get("/openapi.json").json()
    failures = []
    for path, method, _ in _ops(schema):
        if _public(path, method):
            continue
        r = client.request(method.upper(), _url(path))
        ok = r.status_code == 401 and r.headers["content-type"].startswith(
            "application/problem+json"
        )
        if not ok:
            failures.append((method, path, r.status_code))
    assert failures == []


def test_E10S1_oversized_upload_is_refused_before_parsing(
    client: TestClient, login: Callable[[TestClient, str], dict[str, str]]
) -> None:
    h = login(client, "demo.preparer")
    big = b"x" * (3 * 1024 * 1024)  # 3 MB > 2 MB cap (UI-02)
    r = client.post(
        "/v1/cases/CA-2026-0001/files",
        params={"kind": "costs"},
        content=big,
        headers={**h, "Content-Type": "multipart/form-data; boundary=zzz"},
    )
    assert r.status_code == 413
    assert r.json()["code"] == "PAYLOAD_TOO_LARGE"


def test_scope51_found_405_lists_every_method_of_the_path(client: TestClient) -> None:
    """Found by Schemathesis (ST204/ST205): RFC 9110 Allow on 405, all routes of the path."""
    r = client.options("/v1/cases")
    assert r.status_code == 405
    assert r.headers["allow"] == "GET, POST"
    assert r.headers["content-type"].startswith("application/problem+json")


def test_scope51_found_paise_beyond_sqlite_integer_is_422_not_500(
    client: TestClient, login: Callable[[TestClient, str], dict[str, str]]
) -> None:
    """Found by Schemathesis: 2**63 paise reached SQLite and raised OverflowError (500)."""
    body = {"msme_name": "x", "order_ref": "x", "order_value_paise": 1,
            "indicative_amount_paise": 2**63, "due_date": "2027-01-01"}  # fmt: skip
    r = client.post("/v1/cases", json=body, headers=login(client, "demo.preparer"))
    assert r.status_code == 422
    assert r.json()["errors"][0]["field"] == "indicative_amount_paise"


# --- Schemathesis (scope #51) -------------------------------------------------------------


@pytest.fixture
def fuzz_app(tmp_path: Path, seeded_template: Path) -> Iterator[Any]:
    db = tmp_path / "fuzz.db"
    shutil.copyfile(seeded_template, db)
    app = create_app(
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            app_env="test",
            jwt_secret="x" * 40,
            case_db=db,
            llm_enabled=False,
            tracing_enabled=False,
            rate_limit="100000/minute",
        )
    )
    yield app


@pytest.fixture
def api_schema(fuzz_app: Any) -> Any:
    return schemathesis.openapi.from_asgi("/openapi.json", fuzz_app).exclude(
        path_regex=r"/events$"  # SSE stream: fuzzed separately would only hold a connection open
    )


schema = schemathesis.pytest.from_fixture("api_schema")


@pytest.mark.slow
@schema.parametrize()
@settings(
    max_examples=8,
    deadline=None,
    derandomize=True,  # same examples every run: CI is reproducible
    database=None,
    suppress_health_check=list(HealthCheck),
)
def test_scope51_schemathesis_fuzz(case: Any, fuzz_app: Any) -> None:
    with TestClient(fuzz_app) as c:
        token = c.post(
            "/v1/auth/token", json={"username": "demo.preparer", "password": PASSWORD}
        ).json()["access_token"]
    case.call_and_validate(
        headers={"Authorization": f"Bearer {token}"},
        excluded_checks=[
            schemathesis.specs.openapi.checks.positive_data_acceptance,  # 404/409 on valid shapes
            schemathesis.specs.openapi.checks.negative_data_rejection,
        ],
    )
