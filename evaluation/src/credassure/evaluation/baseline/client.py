"""Minimal OpenAI-compatible chat client for the single-prompt baselines (BRD §12).

The baseline is the control, so it deliberately bypasses the product's LLM layer (packages/llm): no
structured-output repair, no guardrails, no retrieval. The OpenAI SDK stays confined to packages/llm;
this uses plain httpx. Responses are cached by request hash so a re-run costs nothing.
"""

import hashlib
import json
import os
import re
import ssl
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from credassure.llm.resilience import shared_limiter

from ..gold.data import REPO

CACHE = REPO / "evaluation" / "baseline" / "cache"
_THINK = re.compile(r"<think>.*?</think>\s*", re.DOTALL)  # Qwen3 reasoning block


def _verify() -> ssl.SSLContext | bool:
    """EVAL_CA_CERT (else LLM_CA_CERT): CA of the course endpoint's self-signed certificate."""
    ca = os.environ.get("EVAL_CA_CERT") or os.environ.get("LLM_CA_CERT")
    return ssl.create_default_context(cafile=ca) if ca else True


def _headers() -> dict[str, str]:
    key = os.environ.get("EVAL_API_KEY")
    return {"Authorization": f"Bearer {key}"} if key else {}


class InfraError(RuntimeError):
    """The endpoint failed twice (timeout or HTTP error). The item is scored infra_error, not a wrong answer."""


class Chat(Protocol):
    model: str
    endpoint: str

    def complete(
        self, messages: list[dict[str, str]], temperature: float, seed: int
    ) -> tuple[str, int]: ...


@dataclass
class OpenAICompatible:
    endpoint: str = os.environ.get("EVAL_BASE_URL", "http://localhost:11434/v1")
    model: str = os.environ.get("EVAL_MODEL", "llama3.1:8b")
    timeout: float = 180.0

    def available(self) -> bool:
        try:
            r = httpx.get(
                f"{self.endpoint}/models", headers=_headers(), verify=_verify(), timeout=5.0
            )
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def complete(
        self, messages: list[dict[str, str]], temperature: float, seed: int
    ) -> tuple[str, int]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "seed": seed,
        }
        # Added only when set, so earlier cache entries keep their keys.
        if max_tokens := os.environ.get("EVAL_MAX_TOKENS"):
            payload["max_tokens"] = int(max_tokens)  # course endpoint: 512 default, 1024 max
        no_think = os.environ.get("EVAL_DISABLE_THINKING", "").lower() == "true"
        if no_think:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        cached = CACHE / f"{key}.json"
        if cached.exists():
            data = json.loads(cached.read_text(encoding="utf-8"))
        else:
            headers, verify = _headers(), _verify()
            for attempt in range(2):  # one retry, then InfraError; failures are never cached
                shared_limiter().acquire()  # one per-team limiter with the agents (NFR-04)
                try:
                    response = httpx.post(
                        f"{self.endpoint}/chat/completions",
                        json=payload,
                        headers=headers,
                        verify=verify,
                        timeout=self.timeout,
                    )
                    response.raise_for_status()
                    break
                except httpx.HTTPError as exc:
                    if attempt:
                        raise InfraError(f"{type(exc).__name__}: {exc}") from exc
            data = response.json()
            CACHE.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(data), encoding="utf-8")
        text = data["choices"][0]["message"]["content"] or ""
        if no_think:
            text = _THINK.sub("", text)
        tokens = int((data.get("usage") or {}).get("total_tokens", 0))
        return text, tokens
