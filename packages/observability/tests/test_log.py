"""Structured JSON logging tests (scope #31, NFR-07 PII never logged raw)."""

import io
import json
import logging
from collections.abc import Iterator

import pytest

from credassure.observability.log import (
    CONTEXT_FIELDS,
    configure_logging,
    log_context,
    set_redactor,
)


@pytest.fixture
def stream() -> Iterator[io.StringIO]:
    buf = io.StringIO()
    configure_logging(level="INFO", stream=buf)
    yield buf
    set_redactor(None)


def records(buf: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buf.getvalue().splitlines()]


def test_NFR07_log_record_has_required_fields(stream: io.StringIO) -> None:
    with log_context(
        request_id="req-1",
        tenant_id="default",
        case_id="CA-2026-0001",
        trace_id="tr-1",
        agent="lendwise",
        stage="lendwise",
    ):
        logging.getLogger("credassure.test").info("stage started")
    (rec,) = records(stream)
    assert rec["message"] == "stage started"
    assert rec["level"] == "INFO"
    assert rec["case_id"] == "CA-2026-0001"
    assert rec["agent"] == "lendwise"
    for field in ("ts", "logger", *CONTEXT_FIELDS):
        assert field in rec


def test_log_context_is_cleared_after_block(stream: io.StringIO) -> None:
    with log_context(case_id="CA-2026-0001"):
        pass
    logging.getLogger("credassure.test").info("outside")
    (rec,) = records(stream)
    assert rec["case_id"] is None


@pytest.mark.parametrize(
    "raw",
    [
        "ABCDE1234F",  # PAN format
        "2345 6789 0123",  # Aadhaar format, spaced
        "234567890123",  # Aadhaar format, unspaced
        "account no 123456789012345",  # bank account near keyword
        "account number is 123456789012345",
        "abcde1234f",  # lower-case PAN
        "sbin0001234",  # lower-case IFSC
        "+91 98765 43210",  # spaced phone
        "9876543210",
    ],
)
def test_NFR07_log_redacts_identifiers(stream: io.StringIO, raw: str) -> None:
    logging.getLogger("credassure.test").info("user said %s", raw)
    out = stream.getvalue()
    assert raw not in out
    assert "[REDACTED" in out


def test_NFR07_log_redacts_extra_fields_and_exceptions(stream: io.StringIO) -> None:
    log = logging.getLogger("credassure.test")
    try:
        raise ValueError("bad PAN ABCDE1234F")
    except ValueError:
        log.exception("failed", extra={"detail": "pan ABCDE1234F"})
    assert "ABCDE1234F" not in stream.getvalue()


def test_NFR07_log_redacts_extra_mapping_keys(stream: io.StringIO) -> None:
    logging.getLogger("credassure.test").info("x", extra={"detail": {"ABCDE1234F": "v"}})
    assert "ABCDE1234F" not in stream.getvalue()


def test_uvicorn_loggers_are_routed_through_json_handler(stream: io.StringIO) -> None:
    logging.getLogger("uvicorn.access").info("GET /v1/cases?pan=ABCDE1234F")
    (rec,) = records(stream)
    assert rec["logger"] == "uvicorn.access"
    assert "ABCDE1234F" not in rec["message"]


def test_set_redactor_replaces_default(stream: io.StringIO) -> None:
    set_redactor(lambda text: text.replace("secret", "***"))
    logging.getLogger("credassure.test").info("a secret value")
    assert records(stream)[0]["message"] == "a *** value"
