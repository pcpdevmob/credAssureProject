"""Operational telemetry: browser error reports and Prometheus metrics (ARCHITECTURE §8.8).

`POST /v1/client-errors` lets the web app report a crash. The report is redacted and written to
the same JSON log as server errors (with the request id it carried, if any); it never reaches
the model, the ledger or the audit log. `GET /v1/metrics` is the evaluator's Prometheus scrape.
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Request, Response
from limits import parse
from pydantic import BaseModel, Field

from credassure.core.errors import ApiErrorCode
from credassure.gateway.deps import User, role
from credassure.gateway.metrics import Metrics
from credassure.gateway.problems import ProblemError
from credassure.security.auth import Principal, Role
from credassure.security.pii import redact

router = APIRouter(prefix="/v1", tags=["telemetry"])
Evaluator = Annotated[Principal, role(Role.EVALUATOR)]
_log = logging.getLogger("credassure.client")
CLIENT_ERRORS = parse("10/minute")  # per user


class ClientError(BaseModel):
    kind: Literal["error", "unhandledrejection", "render"]
    message: str = Field(max_length=500)
    page: str = Field(default="", max_length=200, description="route only, no query string")
    stack: str = Field(default="", max_length=4000)
    request_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    digest: str | None = Field(default=None, pattern=r"^[\w-]{1,64}$", description="Next.js digest")


def _metrics(request: Request) -> Metrics:
    m: Metrics = request.app.state.metrics
    return m


@router.post("/client-errors", status_code=204)
def client_error(body: ClientError, who: User, request: Request) -> Response:
    """A signed-in user's browser reports an error: redacted, logged at WARNING with the user id
    (so a report tied to someone else's request id is traceable), 204. At most 10 a minute per
    user; more are dropped with 429 so the endpoint cannot flood the log."""
    if not request.app.state.client_error_limiter.hit(CLIENT_ERRORS, who.user_id):
        raise ProblemError(429, "too many error reports; wait a minute", ApiErrorCode.RATE_LIMITED)
    _metrics(request).client_error(body.kind)
    _log.warning(
        "client error",
        extra={
            "kind": body.kind,
            "client_message": redact(body.message),
            "page": redact(body.page.split("?", 1)[0]),
            "stack": redact(body.stack),
            "client_request_id": body.request_id,
            "digest": body.digest,
            "role": who.role.value,
            "user_id": who.user_id,
        },
    )
    return Response(status_code=204)


@router.get(
    "/metrics",
    response_class=Response,
    responses={200: {"content": {"text/plain": {}}, "description": "Prometheus text format"}},
)
def metrics(who: Evaluator, request: Request) -> Response:
    return Response(
        _metrics(request).render(), media_type="text/plain; version=0.0.4; charset=utf-8"
    )
