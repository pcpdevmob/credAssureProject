"""SUP-02: chat input is a copilot question, a data correction or an approval action (code, no
model). A correction or an approval typed into chat changes nothing: the reply is fixed text that
names the form or the decision screen. S18 fixtures: data/frozen/v1/intents (DATA_SPEC §8.1).
"""

import json
from datetime import date
from pathlib import Path

import pytest

from credassure.agents.copilot import policy
from credassure.agents.copilot.agent import (
    APPROVAL_REPLY,
    CORRECTION_CLARIFY,
    FORM_NAME,
    answer,
)
from credassure.agents.copilot.intent import APPROVAL_ACTION, DATA_CORRECTION, chat_action
from credassure.guardrails.injection import scan
from credassure.llm.fake import FakeLLM

from .test_v3 import Tools

ROOT = Path(__file__).resolve().parents[4]
S18 = [
    json.loads(x)
    for x in (ROOT / "data/frozen/v1/intents/data_correction.jsonl").open(encoding="utf-8")
]


def _rows(path: str) -> list[dict[str, object]]:
    return [json.loads(x) for x in (ROOT / path).open(encoding="utf-8") if x.strip()]


@pytest.mark.parametrize("row", S18, ids=[r["id"] for r in S18])
def test_SUP02_S18_data_corrections_are_recognised_with_file_and_stage(row: dict[str, str]) -> None:
    action = chat_action(row["message"])
    assert action is not None and action.intent == DATA_CORRECTION
    assert action.clarify is row["expected_clarification"]
    assert action.file_kind == row["expected_file_kind"]
    assert action.reopen_stage == row["expected_reopen_stage"]


def test_SUP02_S18_field_accuracy_is_reported() -> None:
    """BRD SUP-02 acceptance: classifier accuracy reported. Fields are a hint for the reply, so a
    miss costs nothing; the number is kept honest here (in-sample: the rules were written from
    the DATA_SPEC §8.1 description and checked on these 15 rows)."""
    named = [r for r in S18 if not r["expected_clarification"]]
    right = sum((a := chat_action(r["message"])) is not None and a.field == r["expected_field"]
                for r in named)  # fmt: skip
    assert len(named) == 12 and right >= 11, right


@pytest.mark.parametrize(
    "message",
    [
        "Approve it now",
        "Please approve this proposal.",
        "I approve this case",
        "Reject this proposal",
        "Can you reject it?",
        "Return it to the preparer",
        "Send it back, the buffer is missing",
        "Go ahead and sign off on CA-2026-0016",
    ],
)
def test_SUP02_an_approval_typed_into_chat_is_an_action_never_a_decision(message: str) -> None:
    assert chat_action(message) == chat_action(message.upper())
    action = chat_action(message)
    assert action is not None and action.intent == APPROVAL_ACTION


@pytest.mark.parametrize(
    "message",
    [
        "Who approves this case?",
        "How do I approve a proposal?",
        "Can the Director approve a proposal above ₹1.5 crore?",
        "What happens after I reject a proposal?",
        "How do I upload a corrected file?",
        "Why was the report regenerated?",
        "My case is stuck, what should I fix?",
        "Is GST charged on loan processing fees?",
        "What is the status of this case?",
        "Why is the cheapest-looking lender not ranked first?",
        "RBI updated the MSME Master Direction in February 2026. What changed?",
        "What does our approval matrix say about the ₹1.5 crore threshold?",
        "Tell me about CGTMSE fees",
    ],
)
def test_SUP02_questions_stay_questions(message: str) -> None:
    assert chat_action(message) is None


def test_SUP02_no_evaluation_question_is_taken_for_an_action() -> None:
    """Read-only guard, never tuned on (as test_CP07_frozen_regulatory_items...): every question
    the evaluation sends to the copilot, unless the refusal policy or the injection scan already
    answers it, is still routed as a question. So no scored answer path changes."""
    questions: list[tuple[str, str]] = []
    for item in _rows("evaluation/testset/v1/items.jsonl"):
        q = (item.get("input") or {}).get("question")  # type: ignore[union-attr]
        if q:
            questions.append((str(item["id"]), str(q)))
    for path in ("evaluation/retrieval/v1/queries.jsonl", "evaluation/retrieval/dev/queries.jsonl"):
        questions += [(str(r["id"]), str(r["query"])) for r in _rows(path)]
    questions += [
        (str(r["id"]), str(r["question"])) for r in _rows("evaluation/copilot/dev/routing.jsonl")
    ]
    questions += [
        (str(r["id"]), str(r["prompt"])) for r in _rows("evaluation/redteam/prompts.jsonl")
    ]
    questions += [
        (str(r["id"]), str(r["input"]["message"]))  # type: ignore[index]
        for r in _rows("evaluation/safety_v2/items.draft.jsonl")
        if r["kind"] == "chat"
    ]
    assert len(questions) >= 150
    taken = [
        (qid, q)
        for qid, q in questions
        if chat_action(q) is not None
        and not scan(q)
        and policy.check(q, case_id="CA-2026-0001", offer_ids=(), as_of=date(2026, 11, 15)) is None
    ]
    assert taken == []


def test_SUP02_a_correction_reply_names_the_form_and_touches_no_tool_and_no_model() -> None:
    llm, tools = FakeLLM(), Tools("CA-2026-0016")
    r = answer(
        "The minimum buffer should be ₹12 lakh, not ₹10 lakh.",
        case_id="CA-2026-0016",
        tools=tools,
        llm=llm,
        history=(),
        offer_ids=(),
        as_of=date(2026, 11, 15),
    )
    assert (r.intent, r.routed_by, r.source) == (DATA_CORRECTION, "code", "code")
    assert FORM_NAME["opening_position"] in r.answer and "Funding need step" in r.answer
    assert "can't change case data from chat" in r.answer
    assert tools.calls == [] and llm.calls == []
    assert not r.refused and not r.abstained and r.citations == ()


@pytest.mark.parametrize(
    ("message", "reply", "intent"),
    [
        ("Some numbers look off.", CORRECTION_CLARIFY, DATA_CORRECTION),
        ("Approve it now", APPROVAL_REPLY, APPROVAL_ACTION),
    ],
)
def test_SUP02_clarification_and_approval_replies_are_fixed_text_with_the_model_off(
    message: str, reply: str, intent: str
) -> None:
    tools = Tools("CA-2026-0016")
    r = answer(
        message,
        case_id="CA-2026-0016",
        tools=tools,
        llm=None,
        history=(),
        offer_ids=(),
        as_of=date(2026, 11, 15),
    )
    assert (r.answer, r.intent) == (reply, intent)
    assert tools.calls == []
