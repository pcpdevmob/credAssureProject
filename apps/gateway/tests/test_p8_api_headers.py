"""P8.4 (scope #52, OWASP API8): every /v1 response carries no-sniff, no-frame, a deny-all CSP and
no-store; a route's own header (the report CSP, SSE cache control) is kept."""

from collections.abc import Callable
from typing import Any


def test_P8_v1_responses_carry_security_headers(
    client: Any, login: Callable[..., dict[str, str]]
) -> None:
    for r in (
        client.get("/v1/health/live"),
        client.post("/v1/auth/token", json={"username": "nobody", "password": "wrong-password"}),
        client.get("/v1/cases", headers=login(client, "prep.e001")),
    ):
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Content-Security-Policy"].startswith("default-src 'none'")
        assert r.headers["Cache-Control"] == "no-store"
        assert r.headers["Referrer-Policy"] == "no-referrer"


def test_P8_docs_page_is_not_given_the_deny_all_csp(client: Any) -> None:
    assert "Content-Security-Policy" not in client.get("/docs").headers
