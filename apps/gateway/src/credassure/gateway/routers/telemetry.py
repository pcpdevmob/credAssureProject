"""Operational telemetry: browser error reports and Prometheus metrics (ARCHITECTURE §8.8).

`POST /v1/client-errors` lets the web app report a crash. The report is redacted and written to
the same JSON log as server errors (with the request id it carried, if any); it never reaches
the model, the ledger or the audit log. `GET /v1/metrics` is the evaluator's Prometheus scrape.
"""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from credassure.gateway.deps import User, role
from credassure.gateway.metrics import Metrics
from credassure.security.auth import Principal, Role
from credassure.security.pii import redact

router = APIRouter(prefix="/v1", tags=["telemetry"])
Evaluator = Annotated[Principal, role(Role.EVALUATOR)]
_log = logging.getLogger("credassure.client")


class ClientError(BaseModel):
    kind: Literal["error", "unhandledrejection", "render"]
    message: str = Field(max_length=500)
    page: str = Field(default="", max_length=200, description="route only, no query string")
    stack: str = Field(default="", max_length=4000)
    request_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    digest: str | None = Field(default=None, max_length=64, description="Next.js error digest")


def _metrics(request: Request) -> Metrics:
    m: Metrics = request.app.state.metrics
    return m


@router.post("/client-errors", status_code=204)
def client_error(body: ClientError, who: User, request: Request) -> Response:
    """A signed-in user's browser reports an error. Logged redacted at ERROR; 204, no body."""
    _metrics(request).client_error(body.kind)
    _log.error(
        "client error",
        extra={
            "kind": body.kind,
            "client_message": redact(body.message),
            "page": redact(body.page.split("?", 1)[0]),
            "stack": redact(body.stack),
            "client_request_id": body.request_id,
            "digest": body.digest,
            "role": who.role.value,
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
