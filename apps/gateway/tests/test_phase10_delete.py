"""Scope #39, ADR 0025: DELETE /v1/cases/{id} removes the case content, keeps the append-only
record (ledger_facts, approvals, audit_log) and a tombstone; the chain still verifies (OBJ-08)."""

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from credassure.ledger import reads
from credassure.ledger.session import transaction

Login = Callable[[TestClient, str], dict[str, str]]


def _count(client: Any, sql: str, case_id: str) -> int:
    with transaction(client.app.state.services.engine) as s:
        return int(s.execute(text(sql), {"c": case_id}).scalar_one())


def _delete(client: TestClient, h: dict[str, str], case_id: str, version: int | None = None) -> Any:
    if version is None:
        version = client.get(f"/v1/cases/{case_id}", headers=h).json()["row_version"]
    return client.delete(f"/v1/cases/{case_id}", params={"expected_version": version}, headers=h)


def test_scope39_OBJ08_BR14_delete_keeps_record_removes_content_and_chain_verifies(
    client: TestClient, login: Login, run_case: Callable[[TestClient], str]
) -> None:
    case_id = run_case(client)
    p, e = login(client, "demo.preparer"), login(client, "demo.evaluator")
    client.post(f"/v1/cases/{case_id}/chat", json={"message": "What is a KFS?"}, headers=p)
    facts = _count(client, "SELECT count(*) FROM ledger_facts WHERE case_id=:c", case_id)
    assert facts > 0
    assert _count(client, "SELECT count(*) FROM case_files WHERE case_id=:c", case_id) > 0

    r = _delete(client, e, case_id)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "DELETED"

    for table in ("case_files", "chat_messages", "stage_runs", "jobs"):
        assert _count(client, f"SELECT count(*) FROM {table} WHERE case_id=:c", case_id) == 0  # noqa: S608
    assert _count(client, "SELECT count(*) FROM ledger_facts WHERE case_id=:c", case_id) == facts
    tomb = "SELECT count(*) FROM cases WHERE id=:c AND status='DELETED' AND msme_name='[deleted]'"
    assert _count(client, tomb, case_id) == 1
    with transaction(client.app.state.services.engine) as s:
        assert reads.verify_chain(s) == []
        thread = f"{client.app.state.services.settings.tenant_id}:{case_id}"
        left = s.execute(text("SELECT count(*) FROM checkpoints WHERE thread_id=:t"), {"t": thread})
        assert left.scalar_one() == 0  # LangGraph state for the case is gone too

    # invisible everywhere, except the evaluator's audit view of the tombstone
    for h in (p, e):
        assert client.get(f"/v1/cases/{case_id}", headers=h).status_code == 404
        assert case_id not in {
            c["case_id"] for c in client.get("/v1/cases", headers=h).json()["items"]
        }
    assert client.post(f"/v1/cases/{case_id}/run", headers=p).status_code == 404
    audit = client.get(f"/v1/cases/{case_id}/audit", headers=e).json()
    assert audit["events"][-1]["event_type"] == "CASE_DELETED"
    assert audit["chain_ok"] is True
    assert _delete(client, e, case_id, version=0).status_code == 404  # already gone


def test_scope39_only_an_evaluator_deletes(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    r = _delete(client, login(client, "demo.preparer"), case_id)
    assert r.status_code == 403
    assert r.json()["code"] == "FORBIDDEN"


def test_scope39_stale_version_is_409(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    e = login(client, "demo.evaluator")
    version = client.get(f"/v1/cases/{case_id}", headers=e).json()["row_version"]
    assert _delete(client, e, case_id, version=version + 1).status_code == 409


def test_scope39_demo_reset_purge_still_removes_a_tombstone(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    """make demo-reset purges with scripts/purge_cases.py; a tombstone must not block it."""
    import importlib.util
    import sys
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "scripts" / "purge_cases.py"
    spec = importlib.util.spec_from_file_location("purge_cases_t", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["purge_cases_t"] = mod
    spec.loader.exec_module(mod)
    case_id = new_case(client)
    assert _delete(client, login(client, "demo.evaluator"), case_id).status_code == 200
    with transaction(client.app.state.services.engine) as s:
        assert mod.purge(s, [case_id], dry_run=False)["cases"] == 1
    with transaction(client.app.state.services.engine) as s:
        assert reads.verify_chain(s) == []


def test_scope39_nothing_is_written_into_a_tombstone(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    """A job claimed before the delete, or a racing upload, never writes to the tombstone."""
    import pytest

    from credassure.ledger.errors import ConflictError

    case_id = new_case(client)
    svc: Any = client.app.state.services  # type: ignore[attr-defined]
    job = svc.ledger.create_job(case_id, kind="run", stage=None, idempotency_key=None, actor="t")
    assert _delete(client, login(client, "demo.evaluator"), case_id).status_code == 200
    svc.jobs.execute(job.id, case_id, None)
    assert _count(client, "SELECT count(*) FROM stage_runs WHERE case_id=:c", case_id) == 0
    with pytest.raises(ConflictError, match="deleted"):
        svc.ledger.store_case_file(case_id, "costs", "[]", "t", sha256="0" * 64)
