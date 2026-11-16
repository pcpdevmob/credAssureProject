"""Verification Critic through the API (VER-01..05, scope #21, ARCHITECTURE §6.3).

Every stage narrative is checked by the Critic; banned wording or an invented reason in a model
draft drives regeneration and then the template; a narrative that disagrees with the ledger later
is caught at the Critic stage and its stage reopened. Chat answers pass the Critic too."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_lw_items import extraction_reply, start

from credassure.ledger import reads, session

DRAFT_OK = "{rank1.offer} ranks first, with a true annual cost of {rank1.apr}. {excluded.OF-01-C}."


def events(client: Any, case_id: str) -> list[dict[str, Any]]:
    with session.transaction(session.case_engine(client.db)) as s:
        return [
            {"type": e.event_type, **e.payload} for e in reads.audit_events(s, "default", case_id)
        ]


def lw_result(client: Any, case_id: str, h: dict[str, str]) -> dict[str, Any]:
    r = client.get(f"/v1/agents/lendwise/cases/{case_id}/result", headers=h)
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


def test_VER05_CA0005_kind_invented_reason_is_regenerated(make_client: Any, login: Any) -> None:
    """The 9c live run kept a draft with an invented qualitative reason (CA-2026-0005); the
    Critic now blocks it and the regenerated draft (built from slots only) is used."""
    client = make_client(llm_enabled=True, rate_limit="10000/minute")
    invented = (
        "{rank1.offer} ranks first because its repayment terms are flexible. {excluded.OF-01-C}."
    )
    client.llm.replies = {
        "lw_kfs_extract": [extraction_reply("CA-2026-0001")],
        "lw_explain": [invented],
        "regenerate": [DRAFT_OK],
    }
    case_id, h = start(client, login, "CA-2026-0001")
    client.post(f"/v1/agents/lendwise/cases/{case_id}/run", headers=h)
    result = lw_result(client, case_id, h)
    assert result["narrative"].startswith("OF-01-B ranks first, with a true annual cost of")
    assert "flexible" not in result["narrative"]
    assert result["prompt_versions"].get("regenerate") == "1.0.0"
    blocked = [e for e in events(client, case_id) if e["type"] == "CRITIC_BLOCKED"]
    assert [e["codes"] for e in blocked] == [["VER_UNSUPPORTED_REASON"]]


def test_VER05_two_failed_regenerations_fall_back_to_the_template(
    make_client: Any, login: Any
) -> None:
    client = make_client(llm_enabled=True, rate_limit="10000/minute")
    bad = DRAFT_OK + " We recommend you take it."
    client.llm.replies = {
        "lw_kfs_extract": [extraction_reply("CA-2026-0001")],
        "lw_explain": [bad],
        "regenerate": [bad],
    }
    case_id, h = start(client, login, "CA-2026-0001")
    client.post(f"/v1/agents/lendwise/cases/{case_id}/run", headers=h)
    result = lw_result(client, case_id, h)
    assert result["narrative"].startswith("OF-01-B ranks first with an APR of")  # the template
    kinds = [e["type"] for e in events(client, case_id)]
    assert kinds.count("CRITIC_BLOCKED") == 3 and kinds.count("CRITIC_FALLBACK") == 1


@pytest.mark.parametrize("llm_enabled", [False, True])
def test_VER01_ARCH63_critic_stage_reopens_lendwise_for_an_altered_narrative(
    make_client: Any, login: Any, llm_enabled: bool
) -> None:
    client = make_client(llm_enabled=llm_enabled, rate_limit="10000/minute")
    if client.llm is not None:
        client.llm.replies = {"lw_kfs_extract": [extraction_reply("CA-2026-0001")]}
    case_id, h = start(client, login, "CA-2026-0001")
    client.post(f"/v1/agents/lendwise/cases/{case_id}/run", headers=h)
    ledger = client.app.state.services.ledger
    stored = json.loads(ledger.get(case_id, "lw.narrative"))
    stored["text"] += " The total cost is ₹1,11,111."  # altered after LendWise ran
    ledger.put_fact(
        case_id,
        "lw.narrative",
        json.dumps(stored),
        unit="json",
        source_type="narrative",
        source_ref="tamper",
        produced_by="test",
    )
    r = client.post(f"/v1/agents/critic/cases/{case_id}/run", headers=h)
    assert r.status_code == 202, r.text
    kinds = [e["type"] for e in events(client, case_id)]
    assert "CRITIC_REROUTE" in kinds
    findings = client.get(f"/v1/agents/critic/cases/{case_id}/findings", headers=h).json()
    assert findings["decision"] == "GO"  # LendWise re-ran and rewrote its narrative
    assert "₹1,11,111" not in lw_result(client, case_id, h)["narrative"]


def test_CP02_VER01_chat_answer_passes_the_critic(client: Any, login: Any) -> None:
    case_id, h = start(client, login, "CA-2026-0001")
    r = client.post(f"/v1/cases/{case_id}/chat", json={"message": "What is a KFS?"}, headers=h)
    assert r.status_code == 200
    assert r.json()["answer"] == "I can't verify that from the available sources."
    verify = client.app.state.services.verify_claims
    assert verify(case_id, r.json()["answer"]) == []
    assert verify(case_id, "Your loan is pre-approved at 7%.") != []
