"""Phase 9a / E5: the 10 frozen onboarding items (T026-T035) through the API (ONB-01..04, API-01).

Each actor logs in, creates its own case and runs only the onboarding stage. The HR profile is
found from the login binding, never from the request. Gate and failed rules must match gold.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from credassure.agents.onboarding.agent import RULE_NAMES

ROOT = Path(__file__).resolve().parents[3]
ITEMS = [
    item
    for item in map(json.loads, (ROOT / "evaluation/testset/v1/items.jsonl").open())
    if item["category"] == "onboarding"
]
NEW_CASE = {
    "msme_name": "Demo Electronics Pvt Ltd",
    "order_ref": "PO-ONB",
    "order_value_paise": 3_20_00_000_00,
    "indicative_amount_paise": 2_00_00_000_00,
    "due_date": "2027-05-15",
}


def run_item(client: TestClient, login: Callable[..., dict[str, str]], actor: str) -> Any:
    h = login(client, actor)
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    r = client.post(f"/v1/agents/onboarding/cases/{case_id}/run", headers=h)
    assert r.status_code == 202, r.text
    r = client.get(f"/v1/agents/onboarding/cases/{case_id}/result", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("llm_enabled", [False, True])
def test_ONB03_E5_ten_frozen_onboarding_items_through_the_api(
    make_client: Callable[..., Any], login: Callable[..., dict[str, str]], llm_enabled: bool
) -> None:
    client = make_client(llm_enabled=llm_enabled)
    passed = []
    for item in ITEMS:
        drafted = " ".join(
            f"Your {{rule.{r}}} needs action; {{next.{r}}}." for r in item["gold"]["failed_rules"]
        )
        if client.llm is not None:  # S2: a real model path, not only the template fallback
            client.llm.replies = {"onb_explain": [drafted]}
        result = run_item(client, login, item["input"]["actor"])
        failed = sorted(b["field"] for b in result["blockers"])
        assert result["decision"] == item["gold"]["gate"], item["id"]
        assert failed == item["gold"]["failed_rules"], item["id"]
        for rule in failed:  # ONB-04: every failed rule named, model on or off
            assert RULE_NAMES[rule] in result["narrative"], (item["id"], rule)
        if client.llm is not None and failed:  # the model's wording was used, slots rendered
            assert result["narrative"].startswith("Your "), item["id"]
            assert "{" not in result["narrative"], item["id"]
        passed.append(item["id"])
    assert len(passed) == 10


def test_ONB01_preparer_without_an_hr_binding_needs_input(
    client: Any, login: Callable[..., dict[str, str]]
) -> None:
    from credassure.ledger import session

    engine = session.case_engine(client.db)
    with engine.begin() as con:
        con.exec_driver_sql("UPDATE users SET emp_id = NULL WHERE username = 'prep.e001'")
    result = run_item(client, login, "prep.e001")
    assert result["decision"] == "NEEDS_INPUT" and result["question"]


def test_SUP05_onboarding_no_go_is_audited_and_never_advances(
    client: Any, login: Callable[..., dict[str, str]]
) -> None:
    from credassure.ledger import reads, session

    result = run_item(client, login, "prep.e009")
    assert result["decision"] == "NO_GO"
    assert {b["code"] for b in result["blockers"]} == {"ONB_TRAINING_EXPIRED"}
    with session.transaction(session.case_engine(client.db)) as s:  # BR-03
        stages = {r.stage for r in reads.stage_runs(s, "default", result["case_id"])}
        events = [e.event_type for e in reads.audit_events(s, "default", result["case_id"])]
    assert stages == {"onboarding"} and "STAGE_COMPLETED" in events


def test_SUP05_E9S2_wrong_ledger_value_is_overridden_and_audited(
    client: Any, login: Callable[..., dict[str, str]]
) -> None:
    """The agent says GO but writes a wrong fact; the Supervisor's re-check overrides it."""
    from credassure.agents.onboarding import agent as onboarding
    from credassure.core.enums import Stage
    from credassure.ledger import reads, session

    sup = client.app.state.services.supervisor

    def lying(ctx: Any) -> Any:
        result = onboarding.run(ctx)
        ctx.ledger.put_fact(
            ctx.case_id,
            "onb.rule.FIN-101",
            "FAIL",
            unit="enum",
            source_type="hr_record",
            source_ref="tamper",
            produced_by="test",
        )
        return result

    sup.agents = {**sup.agents, Stage.ONBOARDING: lying}
    result = run_item(client, login, "prep.e001")
    assert result["decision"] == "NO_GO"
    assert "SUP_RECHECK_MISMATCH" in {b["code"] for b in result["blockers"]}
    with session.transaction(session.case_engine(client.db)) as s:
        events = [e.event_type for e in reads.audit_events(s, "default", result["case_id"])]
    assert "GATE_OVERRIDE" in events


def test_ONB06_chat_identifiers_are_refused_redacted_and_never_recorded(
    client: Any, login: Callable[..., dict[str, str]]
) -> None:
    from credassure.ledger import reads, session
    from credassure.observability.tracing import capture
    from credassure.security import pii
    from credassure.security.auth import Principal, Role

    body = "52341287650"
    aadhaar = body + pii.verhoeff_digit(body)
    message = f"My Aadhaar is {aadhaar} and PAN ABCDE1234F, am I cleared?"
    h = login(client, "prep.e001")
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    r = client.post(f"/v1/cases/{case_id}/chat", json={"message": message}, headers=h)
    assert r.status_code == 200, r.text
    reply = r.json()
    assert reply["pii_redacted"] is True and "AADHAAR" in reply["notice"]
    assert aadhaar not in r.text and "ABCDE1234F" not in r.text
    clean = client.post(f"/v1/cases/{case_id}/chat", json={"message": "Am I cleared?"}, headers=h)
    assert clean.json()["pii_redacted"] is False and "notice" not in clean.json()

    svc = client.app.state.services.service
    with session.transaction(session.case_engine(client.db)) as s:
        user = reads.user_by_name(s, "prep.e001")
        assert user is not None
        who = Principal(user.id, Role.PREPARER, "default")
        dump = str([e.payload for e in reads.audit_events(s, "default", case_id)])
    with capture() as spans:
        svc.chat(who, case_id, message)
    assert spans and aadhaar not in str(spans) and "[REDACTED_AADHAAR]" in str(spans)
    assert aadhaar not in dump
