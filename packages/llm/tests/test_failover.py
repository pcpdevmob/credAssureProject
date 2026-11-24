"""Model failover for the hosted deployment (deployment plan §5.3, ADR 0008; NFR-01, NFR-04).

The primary endpoint (course Qwen3-8B) is tried first. A call that ends in ModelUnavailable or
LLMTimeout there (connection error, timeout, 5xx after the retries, 401/403/404, or an open circuit)
is sent once to the fallback endpoint (Hugging Face, the same Qwen3-8B). A rejected request (other
4xx) or a spent budget is not retried elsewhere. No network: both clients run over MockTransport.
"""

import logging

import httpx2 as httpx
import pytest

from credassure.llm.client import OpenAICompatLLM
from credassure.llm.failover import FailoverLLM
from credassure.llm.resilience import (
    BudgetExceeded,
    CircuitBreaker,
    LLMError,
    ModelUnavailable,
    RateLimiter,
    stage_budget,
)

from .test_client import Clock, Script, _ok


def client(script: Script, clock: Clock, model: str, failures: int = 5) -> OpenAICompatLLM:
    return OpenAICompatLLM(
        f"http://{model}.test/v1",
        "k",
        model,
        breaker=CircuitBreaker(failures=failures, clock=clock),
        limiter=RateLimiter(6000, clock=clock, sleep=clock.sleep),
        http_client=httpx.Client(transport=httpx.MockTransport(script)),
        sleep=clock.backoff,
    )


def pair(
    primary: Script, fallback: Script, failures: int = 5
) -> tuple[FailoverLLM, OpenAICompatLLM, OpenAICompatLLM]:
    clock = Clock()
    p = client(primary, clock, "course", failures)
    f = client(fallback, clock, "hf", failures)
    return FailoverLLM(p, f), p, f


def test_deploy_primary_answer_is_used_and_fallback_untouched() -> None:
    fallback = Script(_ok("from hf"))
    llm, _, _ = pair(Script(_ok("from course")), fallback)
    assert llm.complete("q") == "from course"
    assert fallback.bodies == []


@pytest.mark.parametrize(
    "failure",
    [httpx.ConnectError("refused"), httpx.Response(503), httpx.Response(401)],
    ids=["connection", "5xx", "bad_key"],
)
def test_deploy_unavailable_primary_fails_over_once(
    failure: Exception | httpx.Response, caplog: pytest.LogCaptureFixture
) -> None:
    fallback = Script(_ok("from hf"))
    llm, _, _ = pair(Script(failure), fallback)
    with caplog.at_level(logging.WARNING, logger="credassure.llm"):
        assert llm.complete("q", name="cp_answer") == "from hf"
    assert len(fallback.bodies) == 1
    assert fallback.bodies[0]["model"] == "hf"
    record = next(r for r in caplog.records if r.getMessage() == "llm failover")
    assert record.prompt == "cp_answer"  # type: ignore[attr-defined]
    assert record.reason in {"ModelUnavailable", "LLMTimeout"}  # type: ignore[attr-defined]


def test_deploy_timeout_on_primary_fails_over() -> None:
    llm, _, _ = pair(Script(httpx.ReadTimeout("slow")), Script(_ok("from hf")))
    assert llm.complete("q") == "from hf"


def test_deploy_rejected_request_is_not_retried_on_the_fallback() -> None:
    """A 400/422 means our request is wrong; the same request would fail on the fallback too."""
    fallback = Script(_ok("from hf"))
    llm, _, _ = pair(Script(httpx.Response(400, json={"error": "bad"})), fallback)
    with pytest.raises(LLMError):
        llm.complete("q")
    assert fallback.bodies == []


def test_deploy_both_down_raises_model_unavailable() -> None:
    llm, _, _ = pair(Script(httpx.ConnectError("x")), Script(httpx.ConnectError("y")))
    with pytest.raises(ModelUnavailable):
        llm.complete("q")


def test_deploy_open_primary_circuit_goes_straight_to_fallback() -> None:
    primary = Script(httpx.Response(503))
    llm, p, _ = pair(primary, Script(_ok("from hf")), failures=1)
    llm.complete("q")  # opens the primary circuit (1 failed call)
    assert p.circuit_state == "open"
    sent = len(primary.bodies)
    assert llm.complete("q") == "from hf"
    assert len(primary.bodies) == sent  # no call to an open circuit


def test_deploy_circuit_reports_open_only_when_both_are_open() -> None:
    """SUP fallback to templates keys on circuit_state == "open" (graph.py, /health/ready)."""
    llm, p, f = pair(Script(httpx.Response(503)), Script(httpx.Response(503)), failures=1)
    assert llm.circuit_state == "closed"
    with pytest.raises(ModelUnavailable):
        llm.complete("q")
    assert (p.circuit_state, f.circuit_state, llm.circuit_state) == ("open", "open", "open")


def test_deploy_circuit_is_closed_while_the_fallback_serves() -> None:
    llm, p, f = pair(Script(httpx.Response(503)), Script(_ok("from hf")), failures=1)
    llm.complete("q")
    assert (p.circuit_state, f.circuit_state, llm.circuit_state) == ("open", "closed", "closed")


def test_deploy_budget_exhaustion_is_not_a_failover() -> None:
    fallback = Script(_ok("from hf"))
    llm, _, _ = pair(Script(_ok("x" * 400, tokens=500)), fallback)
    with stage_budget(10):
        llm.complete("q")  # charged 500 tokens: the stage budget is now spent
        with pytest.raises(BudgetExceeded):
            llm.complete("q")
    assert fallback.bodies == []
