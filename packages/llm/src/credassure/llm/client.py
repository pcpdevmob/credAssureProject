"""OpenAI-compatible client behind LLMPort (ARCHITECTURE §8.7, ADR 0008).

One call = redact the prompt → cache → circuit check → budget check → up to 1 + `retries`
attempts, each through the shared limiter with a 30 s timeout → redact the reply → charge the
budget → cache. Only transient errors (connection, timeout, 429, 5xx) are retried, with full
jitter. A call that fails after its retries counts once against the circuit breaker.
"""

import re
import secrets
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx2
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from credassure.core.prompts import prompt_version
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
_THINK = re.compile(r"<think>.*?</think>\s*", re.DOTALL)  # Qwen3 reasoning block


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
        self._max_tokens, self._no_think = max_tokens, disable_thinking

    @property
    def circuit_state(self) -> str:
        return self.breaker.state

    def complete(
        self, prompt: str, *, name: str = "default", json_schema: Mapping[str, Any] | None = None
    ) -> str:
        messages = [{"role": "user", "content": redact(prompt)}]
        key = cache_key(self.model, name, prompt_version(name), messages, json_schema)
        if self._cache is not None and (hit := self._cache.get(key)) is not None:
            return hit
        budget = current_budget()
        if budget is not None:
            budget.check()
        self.breaker.before_call()  # last check: a half-open probe slot is taken here
        extra: dict[str, Any] = {}
        if self._max_tokens is not None:
            extra["max_tokens"] = self._max_tokens
        if self._no_think:  # vLLM (course endpoint) honours it; Ollama ignores unknown fields
            extra["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
        if json_schema is not None and self._guided:
            extra["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": name, "schema": dict(json_schema)},
            }
        reply = self._send(messages, extra)
        text = reply.choices[0].message.content or ""
        if self._no_think:
            text = _THINK.sub("", text)
        text = redact(text)
        if budget is not None:
            budget.charge(reply.usage.total_tokens if reply.usage else len(prompt + text) // 4)
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
