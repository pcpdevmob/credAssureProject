"""Minimal OpenAI-compatible client behind LLMPort (Phase 8 skeleton).

Phase 6 adds retries with backoff, the response cache, token budget, rate limiter, 30 s timeout
handling and the circuit breaker (ADR 0008). Until then `circuit_state` is always "closed".
"""

from openai import OpenAI


class OpenAICompatLLM:
    circuit_state = "closed"  # ponytail: fixed until the Phase 6 circuit breaker

    def __init__(self, base_url: str, api_key: str | None, model: str, timeout: float = 30.0):
        self._client = OpenAI(base_url=base_url, api_key=api_key or "not-needed", timeout=timeout)
        self._model = model

    def complete(self, prompt: str, *, name: str = "default") -> str:
        reply = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return reply.choices[0].message.content or ""
