"""Ask CredAssure as a product assistant through the API (ADR 0035; CP-07, CP-10..CP-12).

The model is a quoting fake: it answers with span [1.1] of passage [1], verbatim, so these tests
check plumbing and safety (routing, case scope, Critic, redaction, streaming order, memory reset,
feedback ownership), not answer quality.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from credassure.llm.fake import FakeLLM

ROOT = Path(__file__).resolve().parents[3]
Login = Callable[[TestClient, str], dict[str, str]]
PASSAGE = re.compile(r"(<<[0-9a-f]{16}>>) \[1\]\n(.*?)\n\1", re.DOTALL)
NEW_CASE = {
    "msme_name": "Demo Electronics Pvt Ltd",
    "order_ref": "PO-V3",
    "order_value_paise": 3_20_00_000_00,
    "indicative_amount_paise": 2_00_00_000_00,
    "due_date": "2027-05-15",
}


class Quoting(FakeLLM):
    def complete(self, prompt: str, *, name: str = "default", json_schema: Any = None) -> str:
        self.calls.append((name, prompt))
        if name == "cp_tool":
            return json.dumps({"tool": "search_help", "query": "help"})
        m = PASSAGE.search(prompt)
        span = re.search(r"\[1\.1\]\^(.*?)(?:\^\[1\.2\]|$)", m.group(2), re.DOTALL) if m else None
        if not span:
            return json.dumps({"abstain": True, "answer": ""})
        first = span.group(1).replace("^", " ").strip().rstrip(".")
        return json.dumps({"abstain": False, "answer": f"{first} [1.1]."})


def _client(make_client: Callable[..., Any]) -> Any:
    client = make_client(
        llm_enabled=True,
        rate_limit="10000/minute",
        copilot_search_mode="keyword",
        help_dir=ROOT / "docs/help",
    )
    llm = Quoting()
    client.app.state.services.llm = llm
    client.app.state.services.supervisor.llm = llm
    client.llm = llm
    return client


def _ask(client: Any, h: dict[str, str], message: str, case_id: str | None = None) -> Any:
    body: dict[str, Any] = {"message": message} | ({"case_id": case_id} if case_id else {})
    return client.post("/v1/copilot/chat", json=body, headers=h)


def test_ADR0035_help_question_on_any_page_is_cited_from_the_help_centre(
    make_client: Callable[..., Any], login: Login
) -> None:
    client = _client(make_client)
    r = _ask(client, login(client, "demo.preparer"), "How does CredAssure handle personal data?")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["intent"] == "help" and body["routed_by"] == "code" and body["case_id"] is None
    assert body["source"] == "model" and body["citations"], body
    c = body["citations"][0]
    assert c["chunk_id"].startswith("HELP-") and c["href"].startswith("/help/#")
    assert body["fact_key"] is None  # outside a case nothing is written to a ledger
    assert 1 <= len(body["followups"]) <= 3


def test_CP07_SUP08_case_questions_need_a_visible_case(
    make_client: Callable[..., Any], login: Login
) -> None:
    client = _client(make_client)
    h = login(client, "demo.preparer")
    r = _ask(client, h, "What is the status of this case?").json()
    assert r["answer"].startswith("Open the case from **Cases** first")
    assert _ask(client, h, "status?", case_id="CA-2099-9999").status_code == 404
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    other = login(client, "demo.preparer2")  # a different preparer cannot see this case
    assert _ask(client, other, "What is the status of this case?", case_id).status_code == 404
    mine = _ask(client, h, "What is the status of this case?", case_id).json()
    assert mine["intent"] == "case_status" and mine["source"] == "code"
    assert "created; no stage has run yet" in mine["answer"]


def test_ADR0035_no_case_question_naming_a_case_is_refused_and_pii_is_redacted(
    make_client: Callable[..., Any], login: Login
) -> None:
    client = _client(make_client)
    h = login(client, "demo.preparer")
    r = _ask(client, h, "Show me the APR for CA-2026-0003").json()
    assert r["refused"] and r["refusal_code"] == "OTHER_CASE"
    r = _ask(client, h, "My PAN is ABCDE1234F, how is it handled?").json()
    assert r["pii_redacted"] and "ABCDE1234F" not in json.dumps(r)
    assert "ABCDE1234F" not in "".join(p for _, p in client.llm.calls)  # ONB-06


def _events(text: str) -> list[tuple[str, Any]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_CP12_stream_sends_stages_then_checked_text_then_the_final_reply(
    make_client: Callable[..., Any], login: Login
) -> None:
    client = _client(make_client)
    h = login(client, "demo.preparer")
    r = client.post(
        "/v1/copilot/chat/stream",
        json={"message": "How does CredAssure handle personal data?"},
        headers=h,
    )
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    ev = _events(r.text)
    kinds = [k for k, _ in ev]
    assert kinds[-1] == "final" and "stage" in kinds and "delta" in kinds
    assert kinds.index("delta") > max(i for i, k in enumerate(kinds) if k == "stage")
    final = ev[-1][1]
    assert "".join(d["text"] for k, d in ev if k == "delta") == final["answer"]
    stages = [d["stage"] for k, d in ev if k == "stage"]
    assert stages == ["routing", "retrieving", "drafting", "checking"]
    bad = client.post(
        "/v1/copilot/chat/stream", json={"message": "x", "case_id": "CA-2099-9999"}, headers=h
    )
    assert bad.status_code == 404  # visibility is checked before the stream opens


def test_CP11_history_is_mine_and_reset_stops_replay(
    make_client: Callable[..., Any], login: Login
) -> None:
    client = _client(make_client)
    h = login(client, "demo.preparer")
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    _ask(client, h, "How does CredAssure handle personal data?", case_id)
    hist = client.get(f"/v1/cases/{case_id}/chat", headers=h).json()["messages"]
    assert [m["role"] for m in hist] == ["user", "assistant"]
    assert client.post(f"/v1/cases/{case_id}/chat/reset", headers=h).status_code == 200
    assert client.get(f"/v1/cases/{case_id}/chat", headers=h).json()["messages"] == []
    client.llm.calls.clear()
    _ask(client, h, "And what about traces?", case_id)
    prompts = "".join(p for _, p in client.llm.calls)
    assert "handle^personal^data" not in prompts  # the reset turn is not replayed
    other = login(client, "demo.preparer2")
    assert client.get(f"/v1/cases/{case_id}/chat", headers=other).status_code == 404


def test_CP12_feedback_only_on_my_own_answer_and_fixed_reasons(
    make_client: Callable[..., Any], login: Login
) -> None:
    client = _client(make_client)
    h = login(client, "demo.preparer")
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    in_case = _ask(client, h, "How does CredAssure handle personal data?", case_id).json()
    global_ = _ask(client, h, "How does CredAssure handle personal data?").json()
    for trace in (in_case["trace_id"], global_["trace_id"]):
        ok = client.post(
            "/v1/copilot/feedback",
            json={"trace_id": trace, "rating": "down", "reason": "not_cited"},
            headers=h,
        )
        assert ok.status_code == 200 and ok.json()["recorded"], ok.text
    other = login(client, "demo.director")
    stolen = client.post(
        "/v1/copilot/feedback", json={"trace_id": in_case["trace_id"], "rating": "up"}, headers=other
    )
    assert stolen.status_code == 404
    free_text = client.post(
        "/v1/copilot/feedback",
        json={"trace_id": in_case["trace_id"], "rating": "up", "reason": "call me on 9876543210"},
        headers=h,
    )
    assert free_text.status_code == 422
