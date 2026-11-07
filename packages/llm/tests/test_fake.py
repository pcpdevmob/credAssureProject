"""FakeLLM: scripted replies keyed by prompt name; no network (testing rules, scope #15)."""

from credassure.llm.fake import FakeLLM


def test_scope15_reply_is_chosen_by_prompt_name() -> None:
    llm = FakeLLM(replies={"sup_intent": "copilot_question", "wc_explain": "Peak in week 9."})
    assert llm.complete("classify this", name="sup_intent") == "copilot_question"
    assert llm.complete("explain", name="wc_explain") == "Peak in week 9."


def test_scope15_list_replies_are_consumed_in_order() -> None:
    llm = FakeLLM(replies={"lw_kfs_extract": ["first", "second"]})
    assert llm.complete("a", name="lw_kfs_extract") == "first"
    assert llm.complete("b", name="lw_kfs_extract") == "second"


def test_scope15_unknown_name_returns_the_default() -> None:
    assert FakeLLM().complete("anything") == "ok"
    assert FakeLLM(default="fallback").complete("x", name="unscripted") == "fallback"


def test_scope15_calls_are_recorded_as_name_and_prompt() -> None:
    llm = FakeLLM(replies={"sup_plan": "[]"})
    llm.complete("plan please", name="sup_plan")
    llm.complete("hello")
    assert llm.calls == [("sup_plan", "plan please"), ("default", "hello")]


def test_scope48_fake_circuit_is_closed() -> None:
    assert FakeLLM().circuit_state == "closed"
