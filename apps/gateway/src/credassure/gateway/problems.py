"""RFC 9457 problem details for every error (ARCHITECTURE §8.4, scope #32).

Every 4xx/5xx is `application/problem+json` with a stable `code` from `ApiErrorCode`. Internal
errors never leak exception text to the client; the request ID ties the reply to the log line.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from credassure.core.errors import ApiErrorCode
from credassure.ledger.errors import ConflictError
from credassure.ledger.session import RunInProgressError
from credassure.security.auth import AuthError, ForbiddenError
from credassure.tools.registry import RegistryError

_log = logging.getLogger("credassure.gateway")
MEDIA_TYPE = "application/problem+json"

_BY_STATUS = {
    400: ApiErrorCode.VALIDATION_FAILED,
    401: ApiErrorCode.UNAUTHENTICATED,
    403: ApiErrorCode.FORBIDDEN,
    404: ApiErrorCode.NOT_FOUND,
    405: ApiErrorCode.NOT_FOUND,
    409: ApiErrorCode.CONFLICT,
    413: ApiErrorCode.PAYLOAD_TOO_LARGE,
    415: ApiErrorCode.UNSUPPORTED_MEDIA_TYPE,
    422: ApiErrorCode.VALIDATION_FAILED,
    429: ApiErrorCode.RATE_LIMITED,
    500: ApiErrorCode.INTERNAL_ERROR,
    501: ApiErrorCode.NOT_IMPLEMENTED,
}
_TITLES = {
    401: "Unauthenticated",
    403: "Forbidden",
    404: "Not found",
    409: "Conflict",
    413: "Payload too large",
    415: "Unsupported media type",
    422: "Validation failed",
    429: "Too many requests",
    500: "Internal error",
    501: "Not implemented",
}


class ProblemError(Exception):
    """Raise from a route to answer with a problem document."""

    def __init__(
        self,
        status: int,
        detail: str,
        code: ApiErrorCode | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status, self.detail, self.errors = status, detail, errors
        self.code = code or _BY_STATUS.get(status, ApiErrorCode.VALIDATION_FAILED)


def problem_response(
    request: Request,
    status: int,
    detail: str,
    code: ApiErrorCode,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"https://credassure.local/problems/{code.value.lower().replace('_', '-')}",
        "title": _TITLES.get(status, "Error"),
        "status": status,
        "detail": detail,
        "code": code.value,
        "instance": request.url.path,
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type=MEDIA_TYPE)


async def handle(request: Request, exc: Exception) -> JSONResponse:
    """One dispatcher for every error type (fail closed: unknown → 500 with no detail)."""
    if isinstance(exc, ProblemError):
        return problem_response(request, exc.status, exc.detail, exc.code, exc.errors)
    if isinstance(exc, StarletteHTTPException):
        code = _BY_STATUS.get(exc.status_code, ApiErrorCode.VALIDATION_FAILED)
        return problem_response(request, exc.status_code, str(exc.detail), code)
    if isinstance(exc, RequestValidationError):
        errors = [
            {
                "field": ".".join(str(p) for p in e["loc"][1:]) or None,
                "row": None,
                "reason": e["msg"],
            }
            for e in exc.errors()
        ]
        return problem_response(
            request, 422, "request failed validation", ApiErrorCode.VALIDATION_FAILED, errors
        )
    if isinstance(exc, AuthError):
        response = problem_response(request, 401, "not authenticated", ApiErrorCode.UNAUTHENTICATED)
        response.headers["WWW-Authenticate"] = "Bearer"
        return response
    if isinstance(exc, ForbiddenError):
        return problem_response(request, 403, str(exc), ApiErrorCode.FORBIDDEN)
    if isinstance(exc, RunInProgressError):
        return problem_response(
            request, 409, "a run is already in progress for this case", ApiErrorCode.RUN_IN_PROGRESS
        )
    if isinstance(exc, ConflictError):
        return problem_response(request, 409, str(exc), ApiErrorCode.CONFLICT)
    if isinstance(exc, RegistryError):
        return problem_response(request, 403, "tool not allowed", exc.code)
    _log.exception("unhandled error", exc_info=exc)
    return problem_response(request, 500, "internal error", ApiErrorCode.INTERNAL_ERROR)


def install(app: FastAPI) -> None:
    for exc_type in (
        ProblemError,
        StarletteHTTPException,
        RequestValidationError,
        AuthError,
        ForbiddenError,
        RunInProgressError,
        ConflictError,
        RegistryError,
        Exception,
    ):
        app.add_exception_handler(exc_type, handle)
