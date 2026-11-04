"""Structured JSON logging with request/case context and PII masking (scope #31, NFR-07).

Every record is one JSON object carrying the context fields below. All text (message, string
extras, exception text) passes through the active redactor before it is written. The built-in
redactor is a conservative fallback that over-masks; `security.pii.redact` replaces it via
`set_redactor` once the security package exists.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from types import MappingProxyType
from typing import IO, Any

CONTEXT_FIELDS: tuple[str, ...] = (
    "request_id",
    "tenant_id",
    "case_id",
    "trace_id",
    "agent",
    "stage",
)

Redactor = Callable[[str], str]

_context: ContextVar[Mapping[str, str | None]] = ContextVar(
    "credassure_log_context", default=MappingProxyType({})
)

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[REDACTED_EMAIL]"),
    (
        re.compile(r"(?i)\b(a/?c|acct|account)\b[^\d\n]{0,20}\d{9,18}\b"),
        "[REDACTED_ACCOUNT]",
    ),
    (re.compile(r"(?i)\b[A-Z]{5}[0-9]{4}[A-Z]\b"), "[REDACTED_PAN]"),
    (re.compile(r"(?i)\b[A-Z]{4}0[A-Z0-9]{6}\b"), "[REDACTED_IFSC]"),
    (re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"), "[REDACTED_AADHAAR]"),
    (
        re.compile(r"(?<!\d)(\+?91[ -]?)?[6-9]\d{4}[ -]?\d{5}(?!\d)"),
        "[REDACTED_PHONE]",
    ),
)


def default_redact(text: str) -> str:
    """Mask Aadhaar-, PAN-, IFSC-, account-, phone- and email-shaped strings (NFR-07)."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


_redactor: Redactor = default_redact

_STANDARD_ATTRS = frozenset(
    vars(logging.LogRecord("x", logging.INFO, "x", 0, "x", None, None)).keys()
) | {"message", "asctime", "taskName"}


def set_redactor(fn: Redactor | None) -> None:
    """Install the redactor used for every log record; ``None`` restores the default."""
    global _redactor
    _redactor = fn or default_redact


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        return _redactor(value)
    if isinstance(value, int | float | bool) or value is None:
        return value
    if isinstance(value, Mapping):
        return {_redactor(str(k)): _clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_clean(v) for v in value]
    return _redactor(str(value))


class JsonFormatter(logging.Formatter):
    """Render a record as one redacted JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = _context.get()
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _redactor(record.getMessage()),
        }
        for field in CONTEXT_FIELDS:
            payload[field] = ctx.get(field)
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and key not in payload:
                payload[key] = _clean(value)
        if record.exc_info:
            payload["exception"] = _redactor(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


_HANDLER_NAME = "credassure-json"
# Server loggers that install their own handlers; routing them to root keeps them redacted.
_ROUTED_TO_ROOT = ("uvicorn", "uvicorn.error", "uvicorn.access")


def configure_logging(level: str = "INFO", stream: IO[str] | None = None) -> None:
    """Replace the CredAssure root handler with a JSON handler writing to ``stream``."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if handler.get_name() == _HANDLER_NAME:
            root.removeHandler(handler)
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    for name in _ROUTED_TO_ROOT:
        routed = logging.getLogger(name)
        routed.handlers.clear()
        routed.propagate = True


@contextmanager
def log_context(**fields: str | None) -> Iterator[None]:
    """Bind context fields (see CONTEXT_FIELDS) to every record logged inside the block."""
    unknown = set(fields) - set(CONTEXT_FIELDS)
    if unknown:
        raise ValueError(f"unknown log context fields: {sorted(unknown)}")
    token = _context.set({**_context.get(), **fields})
    try:
        yield
    finally:
        _context.reset(token)
