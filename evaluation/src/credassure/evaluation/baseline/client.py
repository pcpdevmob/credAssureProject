"""Minimal OpenAI-compatible chat client for the single-prompt baselines (BRD §12).

The baseline is the control, so it deliberately bypasses the product's LLM layer (packages/llm): no
structured-output repair, no guardrails, no retrieval. The OpenAI SDK stays confined to packages/llm;
this uses plain httpx. Responses are cached by request hash so a re-run costs nothing.
"""

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from ..gold.data import REPO

CACHE = REPO / "evaluation" / "baseline" / "cache"


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
            return httpx.get(f"{self.endpoint}/models", timeout=5.0).status_code == 200
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
        key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        cached = CACHE / f"{key}.json"
        if cached.exists():
            data = json.loads(cached.read_text(encoding="utf-8"))
        else:
            headers = (
                {"Authorization": f"Bearer {os.environ['EVAL_API_KEY']}"}
                if os.environ.get("EVAL_API_KEY")
                else {}
            )
            response = httpx.post(
                f"{self.endpoint}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            CACHE.mkdir(parents=True, exist_ok=True)
            cached.write_text(json.dumps(data), encoding="utf-8")
        text = data["choices"][0]["message"]["content"] or ""
        tokens = int((data.get("usage") or {}).get("total_tokens", 0))
        return text, tokens
