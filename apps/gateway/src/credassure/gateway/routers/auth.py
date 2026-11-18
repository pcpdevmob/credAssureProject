"""Login and identity (NFR-07). Tokens are short-lived; the user row is re-checked per request."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from limits import parse
from pydantic import BaseModel, Field

from credassure.core.errors import ApiErrorCode
from credassure.gateway.deps import Svc, User, bearer_scheme
from credassure.gateway.problems import ProblemError
from credassure.gateway.supervisor_service import acknowledge_notice, notice_state
from credassure.ledger import reads
from credassure.ledger.session import transaction
from credassure.security.auth import (
    AuthError,
    Principal,
    Role,
    hash_password,
    issue_token,
    needs_rehash,
    token_auth_time,
    verify_password,
)

router = APIRouter(prefix="/v1", tags=["auth"])
# A real argon2 hash of a throwaway value: an unknown username costs the same verify (timing).
_DUMMY_HASH = hash_password("credassure-dummy-password-for-timing")
LOGIN_FAILURES = parse("5/minute")  # S4: per username and client IP


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


@router.post("/auth/token")
def token(body: Login, request: Request, svc: Svc) -> dict[str, Any]:
    limiter = request.app.state.login_limiter
    key = (body.username.lower(), request.client.host if request.client else "unknown")
    if not limiter.test(LOGIN_FAILURES, *key):
        raise ProblemError(429, "too many failed logins; wait a minute", ApiErrorCode.RATE_LIMITED)
    with transaction(svc.engine) as s:
        user = reads.user_by_name(s, body.username)
    digest = user.password_hash if user is not None else _DUMMY_HASH
    ok = verify_password(digest, body.password)
    if user is None or not ok or not user.active:
        limiter.hit(LOGIN_FAILURES, *key)  # only failures count, so a busy user is never locked out
        raise AuthError("invalid credentials")
    if needs_rehash(user.password_hash):
        svc.ledger.set_password_hash(user.id, hash_password(body.password))
    secret = svc.settings.jwt_secret
    if secret is None:
        raise AuthError("server has no JWT secret")
    minutes = svc.settings.jwt_expiry_minutes
    who = Principal(user.id, Role(user.role), user.tenant_id)
    return {
        "access_token": issue_token(who, secret.get_secret_value(), minutes),
        "token_type": "bearer",  # nosec B105 - OAuth2 token type name, not a secret
        "expires_in": minutes * 60,
    }


@router.post("/auth/refresh")
def refresh(
    who: User,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    svc: Svc,
) -> dict[str, Any]:
    """H12: swap a still-valid token for a fresh one. The user row was re-checked by `User`
    (deactivated users are refused). The session ends JWT_SESSION_MAX_MINUTES after the password
    was typed; a refresh never extends that, so a stolen token cannot live forever."""
    secret = svc.settings.jwt_secret
    if secret is None:
        raise AuthError("server has no JWT secret")
    if creds is None:  # `User` already refused a missing token; this keeps mypy and readers sure
        raise AuthError("missing bearer token")
    started = token_auth_time(creds.credentials, secret.get_secret_value())
    now = datetime.now(UTC)
    if now - started >= timedelta(minutes=svc.settings.jwt_session_max_minutes):
        raise ProblemError(401, "session is too old; sign in again", ApiErrorCode.UNAUTHENTICATED)
    minutes = svc.settings.jwt_expiry_minutes
    return {
        "access_token": issue_token(
            who, secret.get_secret_value(), minutes, now=now, auth_time=started
        ),
        "token_type": "bearer",  # nosec B105 - OAuth2 token type name, not a secret
        "expires_in": minutes * 60,
    }


@router.get("/me")
def me(who: User, svc: Svc) -> dict[str, Any]:
    with transaction(svc.engine) as s:
        user = reads.get_user(s, who.user_id)
    return {
        "user_id": who.user_id,
        "username": user.username if user else None,
        "role": who.role.value,
    }


@router.get("/me/chat-notice")
def chat_notice(who: User, svc: Svc) -> dict[str, Any]:
    """Scope #40: the copilot first-use notice and whether this user acknowledged this version."""
    return notice_state(svc, who)


@router.post("/me/chat-notice/ack")
def ack_chat_notice(who: User, svc: Svc) -> dict[str, Any]:
    """Scope #40: store the acknowledgement (once per user and notice version, audited)."""
    return acknowledge_notice(svc, who)
