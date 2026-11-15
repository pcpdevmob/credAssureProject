"""Live smoke test: Qwen3 thinking is off on local Ollama (NFR-02/03). Skipped when Ollama is down.

Never part of CI: it needs `ollama serve` with qwen3:8b on this machine (ADR 0017).
"""

import httpx2 as httpx
import pytest

from credassure.llm.client import OpenAICompatLLM

OLLAMA = "http://localhost:11434"


def _up() -> bool:
    try:
        return "qwen3:8b" in httpx.get(f"{OLLAMA}/api/tags", timeout=2).text
    except httpx.HTTPError:
        return False


@pytest.mark.skipif(not _up(), reason="local Ollama with qwen3:8b is not running")
def test_NFR02_live_ollama_short_prompt_returns_under_50_tokens_without_thinking() -> None:
    seen: list[httpx.Response] = []
    client = httpx.Client(event_hooks={"response": [lambda r: seen.append(r)]})
    llm = OpenAICompatLLM(
        f"{OLLAMA}/v1",
        "ollama",
        "qwen3:8b",
        call_timeout=120,
        disable_thinking=True,
        thinking_switch="reasoning_effort",
        http_client=client,
    )
    text = llm.complete("Reply with the single word OK.", name="live_smoke")
    body = seen[-1].read() and seen[-1].json()
    message = body["choices"][0]["message"]
    assert body["usage"]["completion_tokens"] < 50, body["usage"]
    assert not message.get("reasoning") and "<think>" not in text
    assert text.strip()
