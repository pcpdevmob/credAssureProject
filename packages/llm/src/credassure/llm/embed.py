"""OpenAI-compatible embeddings for dense retrieval (KR-02).

Texts are sent in batches through an optional rate limiter (NFR-04). Transient errors are retried
twice with jitter, then raise ModelUnavailable. Vectors are cached by sha256(model + text), so a
re-index embeds only new text (NFR-05). The corpus is public or synthetic: no redaction here.
"""

import hashlib
import json
import secrets
import time
from collections.abc import Callable

import httpx2
from openai import APIConnectionError, InternalServerError, OpenAI, RateLimitError

from credassure.llm.cache import ResponseCache
from credassure.llm.resilience import ModelUnavailable, RateLimiter

_TRANSIENT = (APIConnectionError, RateLimitError, InternalServerError)
_jitter = secrets.SystemRandom()


class OpenAIEmbedder:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        *,
        batch: int = 32,
        retries: int = 2,
        call_timeout: float = 60.0,
        limiter: RateLimiter | None = None,
        cache: ResponseCache | None = None,
        http_client: httpx2.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = OpenAI(
            base_url=base_url,
            api_key=api_key or "not-needed",
            timeout=call_timeout,
            max_retries=0,
            http_client=http_client,
        )
        self.model, self._batch, self._retries = model, batch, retries
        self._limiter, self._cache, self._sleep = limiter, cache, sleep

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"embed\0{self.model}\0{text}".encode()).hexdigest()

    def __call__(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float] | None] = [None] * len(texts)
        todo: list[int] = []
        for i, text in enumerate(texts):
            hit = self._cache.get(self._key(text)) if self._cache else None
            if hit is None:
                todo.append(i)
            else:
                out[i] = json.loads(hit)
        for start in range(0, len(todo), self._batch):
            idx = todo[start : start + self._batch]
            for i, vector in zip(idx, self._send([texts[i] for i in idx]), strict=True):
                out[i] = vector
                if self._cache:
                    self._cache.put(self._key(texts[i]), json.dumps(vector))
        return [v for v in out if v is not None]

    def _send(self, batch: list[str]) -> list[list[float]]:
        for attempt in range(self._retries + 1):
            if self._limiter:
                self._limiter.acquire()
            try:
                reply = self._client.embeddings.create(model=self.model, input=batch)
            except _TRANSIENT as exc:
                if attempt < self._retries:
                    self._sleep(_jitter.uniform(0, 0.5 * 2**attempt))
                    continue
                raise ModelUnavailable(type(exc).__name__) from exc
            return [list(d.embedding) for d in sorted(reply.data, key=lambda d: d.index)]
        raise AssertionError("unreachable")  # pragma: no cover
