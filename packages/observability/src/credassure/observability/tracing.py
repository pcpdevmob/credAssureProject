"""Spans for plans, stages and tool calls (scope #19, ARCHITECTURE §8.8).

``span()`` writes one structured log line per span. Langfuse export is wired by the gateway
(Phase 8b) through ``set_exporter``; tests use ``capture()`` to collect spans in memory.
"""

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_log = logging.getLogger("credassure.trace")
_captured: ContextVar[list[dict[str, Any]] | None] = ContextVar("captured", default=None)
_trace: ContextVar[str | None] = ContextVar("trace", default=None)
_exporter: Callable[[str, dict[str, Any]], None] | None = None


def set_exporter(fn: Callable[[str, dict[str, Any]], None] | None) -> None:
    """Install a span sink (e.g. Langfuse); None turns export off."""
    global _exporter
    _exporter = fn


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[dict[str, Any]]:
    """Yield the span's mutable record (callers may add attributes, e.g. tokens).

    A nested span without a trace_id joins its parent's trace (one trace per run, BRD §14).
    The exporter runs on exit with ``duration_ms`` and ``error`` (exception type or None).
    """
    if attrs.get("trace_id") is None and _trace.get() is not None:
        attrs["trace_id"] = _trace.get()
    record = {"name": name, **attrs}
    sink = _captured.get()
    if sink is not None:
        sink.append(record)
    _log.info("span %s", name, extra={"span": record})
    token = _trace.set(attrs.get("trace_id"))
    started, error = time.perf_counter(), None
    try:
        yield record
    except BaseException as exc:
        error = type(exc).__name__
        raise
    finally:
        _trace.reset(token)
        if _exporter is not None:
            out = {k: v for k, v in record.items() if k != "name"}
            out["duration_ms"] = round((time.perf_counter() - started) * 1000, 3)
            out["error"] = error
            _exporter(name, out)


@contextmanager
def capture() -> Iterator[list[dict[str, Any]]]:
    spans: list[dict[str, Any]] = []
    token = _captured.set(spans)
    try:
        yield spans
    finally:
        _captured.reset(token)
