"""Stable API error codes (scope #32). Routes keep their current HTTP status."""

from enum import StrEnum


class NoPendingApproval(ValueError):  # noqa: N818  # a state, not a failure of the caller
    """The Supervisor is not waiting at the approval interrupt (E11 N2: a core type, so routers
    need not import the concrete Supervisor)."""


class LLMError(Exception):
    """Any failure LLMPort.complete may raise (ADR 0008). Agents catch these, never SDK types."""


class LLMTimeout(LLMError):  # noqa: N818 - names in ADR 0008
    """A model call ran past its 30 s timeout on every attempt (scope #23)."""


class ModelUnavailable(LLMError):  # noqa: N818 - names in ADR 0008
    """The endpoint is failing or the circuit is open: use the template path (scope #48)."""


class BudgetExceeded(LLMError):  # noqa: N818 - names in ADR 0008
    """The stage's token cap is spent (SUP-07, NFR-03)."""


class ApiErrorCode(StrEnum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    STEP_UP_REQUIRED = "STEP_UP_REQUIRED"
    REPORT_STALE = "REPORT_STALE"
    ATTESTATION_REQUIRED = "ATTESTATION_REQUIRED"  # P9: approver did not attest
    NOT_FOUND = "NOT_FOUND"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    COLLECTION_NOT_ALLOWED = "COLLECTION_NOT_ALLOWED"
    CASE_REQUIRED = "CASE_REQUIRED"
    CONFLICT = "CONFLICT"
    RUN_IN_PROGRESS = "RUN_IN_PROGRESS"
    RATE_LIMITED = "RATE_LIMITED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    INTERNAL_ERROR = "INTERNAL_ERROR"
