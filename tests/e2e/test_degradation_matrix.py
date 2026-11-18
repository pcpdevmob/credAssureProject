"""Scope #34 graceful-degradation matrix (P7.4, ARCHITECTURE Q5, ADR 0003 §2, ADR 0008).

Each fault is injected through configuration or the model port; the demo case must still get the
same code-decided outcome (gates, ₹1,42,00,000, Director route, ranking) and the copilot must fail
closed to the exact abstention string, never a 500. docs/evaluation/degradation-matrix.md lists
the faults, the expected behaviour and these test ids.
"""

import json
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from credassure.core.errors import LLMError

PASSWORD = "fixture-password-123"
DEMO = Path(__file__).resolve().parents[2] / "data" / "frozen" / "v1"
KINDS = ("order", "opening_position", "costs", "receipts", "receivables", "payables", "inventory")
ABSTAIN = "I can't verify that from the available sources."


class Down:
    """The model endpoint is unreachable: every call fails; the breaker reports open."""

    circuit_state = "open"

    def complete(self, prompt: str, *, name: str = "default", json_schema: Any = None) -> str:
        raise LLMError("endpoint down")


class Garbage:
    """The model answers, but never with usable structured output."""

    def complete(self, prompt: str, *, name: str = "default", json_schema: Any = None) -> str:
        return "Sure! Here is my answer: ... (no JSON)"


FAULTS: dict[str, dict[str, Any]] = {
    "F1_model_disabled": {"llm_enabled": False},
    "F2_model_down": {"llm": Down()},
    "F3_model_garbage": {"llm": Garbage()},
    "F4_corpus_missing": {"llm": Garbage(), "corpus_db": Path("/nonexistent/corpus.db")},
}


@pytest.fixture
def faulty(tmp_path: Path) -> Iterator[Callable[[dict[str, Any]], TestClient]]:
    stack = ExitStack()

    def _make(fault: dict[str, Any]) -> TestClient:
        from credassure.gateway.main import create_app
        from credassure.gateway.settings import Settings
        from credassure.ledger.seed import seed

        db = tmp_path / "case.db"
        seed(db, {"SEED_PASSWORD": PASSWORD})
        llm = fault.get("llm")
        settings: Any = Settings(
            _env_file=None,
            app_env="test",
            jwt_secret="x" * 40,
            case_db=db,
            llm_enabled=fault.get("llm_enabled", True),
            tracing_enabled=False,
            rate_limit="100000/minute",
            **({"corpus_db": fault["corpus_db"]} if "corpus_db" in fault else {}),
        )
        app = create_app(settings, llm=llm) if llm is not None else create_app(settings)
        return stack.enter_context(TestClient(app))

    yield _make
    stack.close()


def _login(c: TestClient, user: str) -> dict[str, str]:
    r = c.post("/v1/auth/token", json={"username": user, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _demo(c: TestClient, h: dict[str, str]) -> str:
    cid = c.post(
        "/v1/cases",
        json={
            "msme_name": "Degraded Electronics Pvt Ltd",
            "order_ref": "PO-DEG",
            "order_value_paise": 3_20_00_000_00,
            "indicative_amount_paise": 2_00_00_000_00,
            "due_date": "2027-05-15",
        },
        headers=h,
    ).json()["case_id"]
    files = [
        (
            k,
            DEMO
            / "cases/CA-2026-0001"
            / (f"{k}.json" if k in ("order", "opening_position") else f"{k}.csv"),
        )
        for k in KINDS
    ]
    for offer in sorted((DEMO / "offers/CA-2026-0001").glob("*.v1.json")):
        doc = json.loads(offer.read_text())["kfs_doc_id"]
        files += [
            ("offer", offer),
            ("kfs", DEMO / "kfs" / f"{doc}.md"),
            ("kfs", DEMO / "kfs" / f"{doc}-SCH.md"),
        ]
    for kind, path in files:
        mime = {".json": "application/json", ".csv": "text/csv", ".md": "text/markdown"}[
            path.suffix
        ]
        r = c.post(
            f"/v1/cases/{cid}/files",
            params={"kind": kind},
            files={"file": (path.name, path.read_bytes(), mime)},
            headers=h,
        )
        assert r.status_code == 201, (kind, r.text)
    return str(cid)


@pytest.mark.parametrize("fault", sorted(FAULTS))
def test_scope34_Q5_code_decisions_survive_and_copilot_fails_closed(
    faulty: Callable[[dict[str, Any]], TestClient], fault: str
) -> None:
    c = faulty(FAULTS[fault])
    h = _login(c, "demo.preparer")
    cid = _demo(c, h)
    run = c.post(f"/v1/cases/{cid}/run", headers=h)
    assert run.status_code == 202, run.text
    job = c.get(run.json()["status_url"], headers=h).json()
    assert (job["status"], job["outcome"]) == ("succeeded", "AWAITING_APPROVAL"), (fault, job)
    case = c.get(f"/v1/cases/{cid}", headers=h).json()
    assert case["route"] == "director_finance"
    assert all(s["narrative"] for s in case["stages"] if s["stage"] != "critic"), fault  # templates
    funding = c.get(f"/v1/cases/{cid}/funding", headers=h).json()
    assert funding["recommended_amount"]["paise"] == 1_42_00_000_00
    offers = c.get(f"/v1/cases/{cid}/offers", headers=h).json()
    assert offers["gate"] == "GO" and offers["ranking"] == ["OF-01-B", "OF-01-A"]
    chat = c.post(
        f"/v1/cases/{cid}/chat", json={"message": "How is the CGTMSE fee charged?"}, headers=h
    )
    assert chat.status_code == 200 and chat.json()["answer"] == ABSTAIN, (fault, chat.text)
    ready = c.get("/v1/health/ready").json()
    if fault == "F2_model_down":
        assert ready["status"] == "degraded" and ready["checks"]["model"] == "open"
    if fault == "F1_model_disabled":
        assert ready["checks"]["model"] == "disabled"
