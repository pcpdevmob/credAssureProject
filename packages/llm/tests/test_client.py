"""Model client resilience (ARCHITECTURE §8.7, ADR 0008; scope #22, #23, #48; NFR-03/04/05/07).

No network: the OpenAI SDK runs over an httpx MockTransport. Sleeps and clocks are injected.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest

from credassure.llm.cache import ResponseCache
from credassure.llm.client import OpenAICompatLLM
from credassure.llm.resilience import (
    BudgetExceeded,
    CircuitBreaker,
    LLMError,
    LLMTimeout,
    ModelUnavailable,
    RateLimiter,
    stage_budget,
)

PAN = "ABCPE1234F"


def _ok(content: str = "fine", tokens: int = 5) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "x",
            "object": "chat.completion",
            "created": 0,
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": tokens - 1, "total_tokens": tokens},
        },
    )


class Script:
    """Each request takes the next step: an httpx.Response or an exception to raise."""

    def __init__(self, *steps: httpx.Response | Exception) -> None:
        self.steps = list(steps)
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(json.loads(request.content))
        step = self.steps.pop(0) if len(self.steps) > 1 else self.steps[0]
        if isinstance(step, Exception):
            raise step
        return step


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []
        self.backoffs: list[float] = []  # the client's retry sleeps only, not limiter spacing

    def __call__(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.now += s

    def backoff(self, s: float) -> None:
        self.backoffs.append(s)
        self.sleep(s)


def make(script: Script, *, clock: Clock | None = None, **kw: Any) -> tuple[OpenAICompatLLM, Clock]:
    clock = clock or Clock()
    kw.setdefault("breaker", CircuitBreaker(clock=clock))
    kw.setdefault("limiter", RateLimiter(6000, clock=clock, sleep=clock.sleep))
    llm = OpenAICompatLLM(
        "http://model.test/v1",
        "k",
        "m",
        http_client=httpx.Client(transport=httpx.MockTransport(script)),
        sleep=clock.backoff,
        **kw,
    )
    return llm, clock


def test_reply_text_is_returned() -> None:
    llm, _ = make(Script(_ok("hello")))
    assert llm.complete("hi", name="x") == "hello"


@pytest.mark.parametrize(
    "transient",
    [
        httpx.Response(500, json={"error": {"message": "boom"}}),
        httpx.Response(503, json={"error": {"message": "busy"}}),
        httpx.Response(429, json={"error": {"message": "slow down"}}),
        httpx.ConnectError("refused"),
    ],
)
def test_scope48_transient_errors_are_retried_with_backoff(
    transient: httpx.Response | Exception,
) -> None:
    script = Script(transient, transient, _ok("third time"))
    llm, clock = make(script)
    assert llm.complete("hi") == "third time"
    assert len(script.bodies) == 3
    # full jitter: retry n sleeps within [0, 0.5 * 2**n]
    assert len(clock.backoffs) == 2
    assert all(0 <= s <= 0.5 * 2**n for n, s in enumerate(clock.backoffs))


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_scope48_client_errors_are_not_retried(status: int) -> None:
    # 401/403/404 (wrong key, model or URL) raise ModelUnavailable, an LLMError, so the stage
    # falls back to templates; the breaker counts one failure but stays closed.
    script = Script(httpx.Response(status, json={"error": {"message": "no"}}))
    llm, _ = make(script)
    with pytest.raises(LLMError):
        llm.complete("hi")
    assert len(script.bodies) == 1
    assert llm.circuit_state == "closed"  # our bug, not an endpoint outage


def test_scope48_retries_stop_after_two() -> None:
    script = Script(httpx.Response(500, json={}))
    llm, _ = make(script)
    with pytest.raises(ModelUnavailable):
        llm.complete("hi")
    assert len(script.bodies) == 3  # 1 call + 2 retries


def test_scope23_hung_call_times_out_with_LLMTimeout() -> None:
    script = Script(httpx.ReadTimeout("hung"))
    llm, _ = make(script)
    with pytest.raises(LLMTimeout):
        llm.complete("hi")


def test_scope23_call_timeout_defaults_to_30_seconds() -> None:
    llm, _ = make(Script(_ok()))
    assert llm.call_timeout == 30.0


# ---- circuit breaker (#48, ADR 0008) -------------------------------------------------------


def test_scope48_breaker_opens_after_5_consecutive_failed_calls() -> None:
    script = Script(httpx.Response(500, json={}))
    llm, _ = make(script, retries=0)
    for _ in range(4):
        with pytest.raises(ModelUnavailable):
            llm.complete("hi")
        assert llm.circuit_state == "closed"
    with pytest.raises(ModelUnavailable):
        llm.complete("hi")
    assert llm.circuit_state == "open"
    sent = len(script.bodies)
    with pytest.raises(ModelUnavailable):
        llm.complete("hi")
    assert len(script.bodies) == sent  # open: no network call at all


def test_scope48_breaker_half_opens_after_60s_and_closes_on_success() -> None:
    script = Script(*[httpx.Response(500, json={})] * 5, _ok("back"))
    llm, clock = make(script, retries=0)
    for _ in range(5):
        with pytest.raises(ModelUnavailable):
            llm.complete("hi")
    clock.now += 59
    assert llm.circuit_state == "open"
    clock.now += 1
    assert llm.circuit_state == "half_open"
    assert llm.complete("hi") == "back"
    assert llm.circuit_state == "closed"


def test_scope48_failed_probe_reopens_for_another_60s() -> None:
    llm, clock = make(Script(httpx.Response(500, json={})), retries=0)
    for _ in range(5):
        with pytest.raises(ModelUnavailable):
            llm.complete("hi")
    clock.now += 60
    with pytest.raises(ModelUnavailable):
        llm.complete("hi")
    assert llm.circuit_state == "open"


def test_scope48_half_open_lets_exactly_one_probe_through() -> None:
    clock = Clock()
    breaker = CircuitBreaker(failures=1, open_s=60, clock=clock)
    breaker.failure()
    clock.now += 60
    breaker.before_call()  # the probe
    with pytest.raises(ModelUnavailable):
        breaker.before_call()  # a second caller while the probe is in flight
    breaker.success()
    breaker.before_call()
    assert breaker.state == "closed"


def test_scope48_client_error_on_the_probe_does_not_wedge_the_breaker() -> None:
    script = Script(*[httpx.Response(500, json={})] * 5, httpx.Response(400, json={}), _ok("up"))
    llm, clock = make(script, retries=0)
    for _ in range(5):
        with pytest.raises(ModelUnavailable):
            llm.complete("hi")
    clock.now += 60
    with pytest.raises(LLMError):
        llm.complete("hi")  # the endpoint answered: it is up
    assert llm.complete("hi") == "up"


def test_scope48_success_resets_the_failure_count() -> None:
    fail = httpx.Response(500, json={})
    llm, _ = make(Script(fail, fail, fail, fail, _ok(), fail), retries=0)
    for _ in range(4):
        with pytest.raises(ModelUnavailable):
            llm.complete("hi")
    llm.complete("hi")
    with pytest.raises(ModelUnavailable):
        llm.complete("hi")
    assert llm.circuit_state == "closed"


# ---- limiter, budget, cache -------------------------------------------------------------------


def test_scope22_limiter_spaces_calls() -> None:
    clock = Clock()
    lim = RateLimiter(60, clock=clock, sleep=clock.sleep)  # one per second
    for _ in range(3):
        lim.acquire()
    assert clock.slept == [1.0, 1.0]


def test_scope22_every_attempt_goes_through_the_shared_limiter() -> None:
    clock = Clock()
    calls: list[int] = []
    lim = RateLimiter(6000, clock=clock, sleep=clock.sleep)
    original: Callable[[], None] = lim.acquire
    lim.acquire = lambda: (calls.append(1), original())[1]  # type: ignore[method-assign]
    llm, _ = make(Script(httpx.Response(500, json={}), _ok()), clock=clock, limiter=lim)
    llm.complete("hi")
    assert len(calls) == 2


def test_NFR03_tokens_are_charged_to_the_stage_budget() -> None:
    llm, _ = make(Script(_ok(tokens=40)))
    with stage_budget(100) as budget:
        llm.complete("a")
        llm.complete("b")
    assert budget.used == 80


def test_NFR03_spent_budget_refuses_the_next_call() -> None:
    script = Script(_ok(tokens=60))
    llm, _ = make(script)
    with stage_budget(100):
        llm.complete("a")
        llm.complete("b")  # 120 >= 100 after this one
        with pytest.raises(BudgetExceeded):
            llm.complete("c")
    assert len(script.bodies) == 2


def test_NFR05_repeat_call_is_served_from_cache(tmp_path: Path) -> None:
    script = Script(_ok("cached"))
    llm, _ = make(script, cache=ResponseCache(tmp_path / "c.db"))
    assert llm.complete("same", name="p") == "cached"
    assert llm.complete("same", name="p") == "cached"
    assert len(script.bodies) == 1
    llm.complete("different", name="p")
    assert len(script.bodies) == 2


def test_NFR05_cache_key_includes_prompt_version() -> None:
    from credassure.llm.cache import cache_key

    a = cache_key("m", "p", "1.0.0", [{"role": "user", "content": "x"}], None)
    b = cache_key("m", "p", "1.1.0", [{"role": "user", "content": "x"}], None)
    c = cache_key("m2", "p", "1.0.0", [{"role": "user", "content": "x"}], None)
    assert len({a, b, c}) == 3


# ---- PII and guided JSON ----------------------------------------------------------------------


def test_NFR07_prompt_is_redacted_before_it_leaves() -> None:
    script = Script(_ok())
    llm, _ = make(script)
    llm.complete(f"preparer PAN {PAN}")
    assert PAN not in json.dumps(script.bodies[0])
    assert "[REDACTED_PAN]" in script.bodies[0]["messages"][0]["content"]


def test_NFR07_reply_is_redacted_before_it_is_returned() -> None:
    llm, _ = make(Script(_ok(f"their PAN is {PAN}")))
    assert llm.complete("hi") == "their PAN is [REDACTED_PAN]"


def test_guided_json_sends_response_format_only_when_supported() -> None:
    schema = {"type": "object", "properties": {"a": {"type": "integer"}}}
    on = Script(_ok("{}"))
    llm, _ = make(on, guided_json=True)
    llm.complete("x", name="p", json_schema=schema)
    assert on.bodies[0]["response_format"]["json_schema"]["schema"] == schema
    off = Script(_ok("{}"))
    llm, _ = make(off, guided_json=False)
    llm.complete("x", name="p", json_schema=schema)
    assert "response_format" not in off.bodies[0]


def test_scope48_misconfigured_endpoint_falls_back_like_an_outage() -> None:
    llm, _ = make(Script(httpx.Response(404, json={"error": {"message": "no model"}})))
    with pytest.raises(ModelUnavailable):
        llm.complete("hi")


def test_scope36_bump_check_refuses_an_option_as_base() -> None:
    from credassure.core import prompts

    with pytest.raises(SystemExit):
        prompts.main(["check", "--base", "--output=x"])


def test_NFR02_qwen3_thinking_off_is_requested_and_think_block_stripped() -> None:
    script = Script(_ok('<think>\nweighing it\n</think>\n\n{"a": 1}'))
    llm, _ = make(script, disable_thinking=True, max_tokens=1024)
    assert llm.complete("x", name="p") == '{"a": 1}'
    body = script.bodies[0]
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["max_tokens"] == 1024


def test_NFR02_defaults_send_neither_thinking_switch_nor_max_tokens() -> None:
    script = Script(_ok("<think>kept</think>ok"))
    llm, _ = make(script)
    assert llm.complete("x", name="p") == "<think>kept</think>ok"
    assert "chat_template_kwargs" not in script.bodies[0]
    assert "max_tokens" not in script.bodies[0]
