"""Embeddings client (KR-02; NFR-04 limiter, NFR-05 cache). No network: MockTransport."""

import json
from pathlib import Path
from typing import Any

import httpx2 as httpx
import pytest

from credassure.llm.cache import ResponseCache
from credassure.llm.embed import OpenAIEmbedder
from credassure.llm.resilience import ModelUnavailable


def _vectors(request: httpx.Request) -> httpx.Response:
    texts = json.loads(request.content)["input"]
    data = [
        {"object": "embedding", "index": i, "embedding": [float(len(t)), 1.0]}
        for i, t in enumerate(texts)
    ]
    data.reverse()  # the API may return any order; the client sorts by index
    return httpx.Response(
        200,
        json={
            "object": "list",
            "data": data,
            "model": "m",
            "usage": {"prompt_tokens": 1, "total_tokens": 1},
        },
    )


def _embedder(handler: Any, **kw: Any) -> OpenAIEmbedder:
    return OpenAIEmbedder(
        "http://embed.test/v1",
        None,
        "nomic-embed-text",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _s: None,
        **kw,
    )


def test_KR02_embeds_in_input_order_and_batches() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(len(json.loads(request.content)["input"]))
        return _vectors(request)

    out = _embedder(handler, batch=2)(["a", "bbb", "cc"])
    assert out == [[1.0, 1.0], [3.0, 1.0], [2.0, 1.0]]
    assert calls == [2, 1]


def test_NFR05_cached_texts_are_not_sent_again(tmp_path: Path) -> None:
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.extend(json.loads(request.content)["input"])
        return _vectors(request)

    cache = ResponseCache(tmp_path / "embed.db")
    _embedder(handler, cache=cache)(["a", "bb"])
    assert _embedder(handler, cache=cache)(["bb", "a", "new"]) == [
        [2.0, 1.0],
        [1.0, 1.0],
        [3.0, 1.0],
    ]
    assert sent == ["a", "bb", "new"]


def test_NFR04_transient_errors_retry_twice_then_fail_closed() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(503, json={"error": {"message": "busy"}})

    with pytest.raises(ModelUnavailable):
        _embedder(handler)(["a"])
    assert len(attempts) == 3


def test_NFR04_transient_error_then_success() -> None:
    replies = iter([httpx.Response(503, json={"error": {"message": "busy"}})])

    def handler(request: httpx.Request) -> httpx.Response:
        return next(replies, None) or _vectors(request)

    assert _embedder(handler)(["ab"]) == [[2.0, 1.0]]
