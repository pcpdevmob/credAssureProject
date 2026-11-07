"""Spans for plans, stages and tool calls (scope #19, ARCHITECTURE §8.8).

``span()`` writes one structured log line per span. Langfuse export is wired by the gateway
(Phase 8b) through ``set_exporter``; tests use ``capture()`` to collect spans in memory.
"""

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_log = logging.getLogger("credassure.trace")
_captured: ContextVar[list[dict[str, Any]] | None] = ContextVar("captured", default=None)
_exporter: Callable[[str, dict[str, Any]], None] | None = None


def set_exporter(fn: Callable[[str, dict[str, Any]], None] | None) -> None:
    """Install a span sink (e.g. Langfuse); None turns export off."""
    global _exporter
    _exporter = fn


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[None]:
    record = {"name": name, **attrs}
    sink = _captured.get()
    if sink is not None:
        sink.append(record)
    _log.info("span %s", name, extra={"span": record})
    if _exporter is not None:
        _exporter(name, attrs)
    yield


@contextmanager
def capture() -> Iterator[list[dict[str, Any]]]:
    spans: list[dict[str, Any]] = []
    token = _captured.set(spans)
    try:
        yield spans
    finally:
        _captured.reset(token)
