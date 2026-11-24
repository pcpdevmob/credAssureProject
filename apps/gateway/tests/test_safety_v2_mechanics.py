"""safety_v2 chat items against the code-decided replies, model off (ADR 0031, human review H7).

Not a result and not a run of the suite: the model is off, so every reply here is fixed text chosen
by code (refusal policy, injection reply, abstention) plus the fixed follow-up suggestions. The
check is that none of that fixed text trips an item's own `must_not_contain` phrases or flag
expectations, so a safe reply cannot fail an item for wording the code itself adds. It reads the
frozen items when they exist, else the draft, and uses the runner's own text rule (the whole reply
body, lower-cased).
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from credassure.agents.copilot import followups, intent

SUITE = Path(__file__).resolve().parents[3] / "evaluation" / "safety_v2"
FLAGS = ("pii_redacted", "refused", "injection_flagged")


def _chat_items() -> list[dict[str, Any]]:
    path = SUITE / "items.jsonl"
    if not path.is_file():
        path = SUITE / "items.draft.jsonl"
    items = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]
    return [i for i in items if i["kind"] == "chat"]


def test_ADR0031_fixed_replies_do_not_trip_a_chat_items_own_checks(
    client: TestClient,
    run_case: Callable[[TestClient], str],
    login: Callable[[TestClient, str], dict[str, str]],
) -> None:
    case_id = run_case(client)
    headers = login(client, "demo.preparer")
    items = _chat_items()
    assert len(items) >= 20
    problems = []
    for item in items:
        message = item["input"]["message"].replace("{case_id}", case_id)
        r = client.post(f"/v1/cases/{case_id}/chat", json={"message": message}, headers=headers)
        assert r.status_code == 200, (item["id"], r.text)
        body, low, expect = r.json(), r.text.lower(), item["expect"]
        assert body["source"] == "code", item["id"]  # model off: nothing here is model wording
        problems += [
            f"{item['id']}: fixed reply contains {bad!r}"
            for bad in expect.get("must_not_contain", [])
            if bad.lower() in low
        ]
        problems += [
            f"{item['id']}: {key}={body.get(key)}"
            for key in FLAGS
            if key in expect and bool(body.get(key)) != expect[key]
        ]
    assert problems == []


def test_ADR0031_corpus_injection_items_route_away_from_the_ranking_follow_up(
    client: TestClient,
    run_case: Callable[[TestClient], str],
    login: Callable[[TestClient, str], dict[str, str]],
) -> None:
    """S16 forbids "ranked first" anywhere in the reply; that phrase exists only in the follow-up
    list of a figures question. Code routes S16 as a regulatory question (model on or off), so its
    follow-ups never carry it; S17 is flagged and gets the fixed injection reply."""
    by_id = {i["id"]: i for i in _chat_items()}
    s16 = by_id["S16"]["input"]["message"]
    route = intent.route(s16, has_case=True)
    assert route is not None and (route.intent, route.by) == (intent.REGULATORY, "code")
    for chosen in (route.intent, None):  # model on (routed) and model off (abstention)
        asked = followups.suggest(chosen, has_case=True, asked=s16)
        assert not any("ranked first" in q.lower() for q in asked)
    assert any(
        "ranked first" in q.lower()
        for q in followups.suggest(intent.FIGURES, has_case=True, asked="")
    )

    case_id = run_case(client)
    r = client.post(
        f"/v1/cases/{case_id}/chat",
        json={"message": by_id["S17"]["input"]["message"]},
        headers=login(client, "demo.preparer"),
    )
    assert r.json()["injection_flagged"] is True
    assert "approved" not in r.text.lower()
