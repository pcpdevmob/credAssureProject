"""OpenAI-compatible client behind LLMPort (ARCHITECTURE §8.7, ADR 0008).

One call = redact the prompt → cache → circuit check → budget check → up to 1 + `retries`
attempts, each through the shared limiter with a 30 s timeout → redact the reply → charge the
budget → cache. Only transient errors (connection, timeout, 429, 5xx) are retried, with full
jitter. A call that fails after its retries counts once against the circuit breaker.
"""

import logging
import re
import secrets
import time
from collections.abc import Callable, Mapping
from typing import Any, Literal

import httpx2
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from credassure.core.prompts import prompt_max_tokens, prompt_version
from credassure.llm.cache import ResponseCache, cache_key
from credassure.llm.resilience import (
    CircuitBreaker,
    LLMError,
    LLMTimeout,
    ModelUnavailable,
    RateLimiter,
    current_budget,
    shared_limiter,
)
from credassure.security.pii import redact

_TRANSIENT = (APIConnectionError, RateLimitError, InternalServerError)  # timeout ⊂ connection
_jitter = secrets.SystemRandom()
_log = logging.getLogger("credassure.llm")
_THINK = re.compile(r"<think>.*?</think>\s*", re.DOTALL)  # Qwen3 reasoning block
# How each server turns Qwen3 thinking off. Probed 2026-11-15 on Ollama 0.40.16: `/no_think` text
# and `think: false` on /v1 are ignored (148 tokens); `reasoning_effort: "none"` gives 2 tokens.
ThinkingSwitch = Literal["reasoning_effort", "chat_template_kwargs"]
THINKING_OFF: dict[str, dict[str, Any]] = {
    "reasoning_effort": {"reasoning_effort": "none"},  # Ollama OpenAI-compatible route
    "chat_template_kwargs": {"chat_template_kwargs": {"enable_thinking": False}},  # vLLM
}


class OpenAICompatLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        *,
        call_timeout: float = 30.0,
        retries: int = 2,
        breaker: CircuitBreaker | None = None,
        limiter: RateLimiter | None = None,
        cache: ResponseCache | None = None,
        guided_json: bool = False,
        max_tokens: int | None = None,
        disable_thinking: bool = False,
        thinking_switch: ThinkingSwitch = "chat_template_kwargs",
        http_client: httpx2.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key or "not-needed",
            timeout=call_timeout,
            max_retries=0,  # retries are ours: transient only, counted by the breaker
            http_client=http_client,
        )
        self.model, self.call_timeout, self.retries = model, call_timeout, retries
        self.breaker = breaker or CircuitBreaker()
        self._limiter = limiter
        self._cache, self._guided, self._sleep = cache, guided_json, sleep
        self._max_tokens = max_tokens
        self._thinking_off = THINKING_OFF[thinking_switch] if disable_thinking else None

    @property
    def circuit_state(self) -> str:
        return self.breaker.state

    def complete(
        self, prompt: str, *, name: str = "default", json_schema: Mapping[str, Any] | None = None
    ) -> str:
        started = time.monotonic()
        version = prompt_version(name)
        messages = [{"role": "user", "content": redact(prompt)}]
        key = cache_key(self.model, name, version, messages, json_schema)
        if self._cache is not None and (hit := self._cache.get(key)) is not None:
            _log.info("llm call", extra={"prompt": name, "prompt_version": version, "cached": True})
            return hit
        budget = current_budget()
        if budget is not None:
            budget.check()
        self.breaker.before_call()  # last check: a half-open probe slot is taken here
        extra: dict[str, Any] = {}
        caps = [c for c in (self._max_tokens, prompt_max_tokens(name)) if c is not None]
        if caps:
            extra["max_tokens"] = min(caps)
        if self._thinking_off is not None:
            extra["extra_body"] = self._thinking_off
        if json_schema is not None and self._guided:
            extra["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": name, "schema": dict(json_schema)},
            }
        reply = self._send(messages, extra)
        message = reply.choices[0].message
        raw = message.content or ""
        # Safety net: thinking can still arrive inline (<think>) or as Ollama's `reasoning` field.
        # Neither reaches the caller, but both are charged to the budget.
        thought = "".join(_THINK.findall(raw)) + str(
            (message.model_extra or {}).get("reasoning") or ""
        )
        text = redact(_THINK.sub("", raw))
        used = reply.usage.total_tokens if reply.usage else len(prompt + raw + thought) // 4
        if budget is not None:
            budget.charge(used)
        _log.info(
            "llm call",
            extra={
                "prompt": name,
                "prompt_version": version,
                "cached": False,
                "prompt_tokens": reply.usage.prompt_tokens if reply.usage else None,
                "completion_tokens": reply.usage.completion_tokens if reply.usage else None,
                "total_tokens": used,
                "thinking_tokens_est": len(thought) // 4,
                "latency_ms": round((time.monotonic() - started) * 1000),
            },
        )
        if self._cache is not None:
            self._cache.put(key, text)
        return text

    def _send(self, messages: list[dict[str, str]], extra: dict[str, Any]) -> Any:
        limiter = self._limiter or shared_limiter()
        for attempt in range(self.retries + 1):
            limiter.acquire()
            try:
                reply = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,  # type: ignore[arg-type]
                    temperature=0,
                    **extra,
                )
            except _TRANSIENT as exc:
                if attempt < self.retries:
                    self._sleep(_jitter.uniform(0, 0.5 * 2**attempt))
                    continue
                self.breaker.failure()
                if isinstance(exc, APITimeoutError):
                    raise LLMTimeout(f"no reply in {self.call_timeout:g} s") from exc
                raise ModelUnavailable(type(exc).__name__) from exc
            except APIError as exc:
                status = getattr(exc, "status_code", None)
                if status in (401, 403, 404):  # wrong key, model or URL: templates, like an outage
                    self.breaker.failure()
                    raise ModelUnavailable(f"HTTP {status}") from exc
                self.breaker.success()  # other 4xx: our request is bad; the endpoint is up
                raise LLMError(type(exc).__name__) from exc
            self.breaker.success()
            return reply
        raise AssertionError("unreachable")  # pragma: no cover
