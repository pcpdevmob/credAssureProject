"""Sign-in and identity (NFR-07, ADR 0038). Tokens are short-lived; the user row is re-checked per
request, and a bumped token_version revokes every token a user holds.

POST /v1/auth/token answers a FULL token, or a stage token (`stage` "mfa" or "setup") with the
steps still due in `next`. A stage token opens only its own routes:
  mfa   → POST /v1/auth/mfa/verify
  setup → POST /v1/auth/password, /v1/auth/mfa/setup, /v1/auth/mfa/enable, GET /v1/me
Each of those answers the next token, so a client follows `stage` and `next` until FULL.
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from limits import parse
from pydantic import BaseModel, Field, SecretStr

from credassure.core.errors import ApiErrorCode
from credassure.gateway import accounts
from credassure.gateway.deps import (
    Account,
    MfaPending,
    SetupUser,
    Svc,
    User,
    bearer_scheme,
)
from credassure.gateway.problems import ProblemError
from credassure.gateway.supervisor_service import acknowledge_notice, notice_state
from credassure.ledger import reads
from credassure.ledger.models import User as UserRow
from credassure.ledger.session import transaction
from credassure.security import mfa, password_policy
from credassure.security.auth import (
    AuthError,
    hash_password,
    issue_token,
    needs_rehash,
    token_auth_time,
    verify_password,
)

router = APIRouter(prefix="/v1", tags=["auth"])
# A real argon2 hash of a throwaway value: an unknown username costs the same verify (timing).
_DUMMY_HASH = hash_password("credassure-dummy-password-for-timing")
LOGIN_FAILURES = parse("5/minute")  # S4: per username and client IP; per user for codes
# ADR 0038 review: a slower ceiling on the same keys, so a 6-digit code cannot be guessed at
# 5 a minute all day (20 an hour), and a per-username bucket across IPs against spraying.
HOURLY_FAILURES = parse("20/hour")
USERNAME_FAILURES = parse("50/hour")


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class Code(BaseModel):
    code: SecretStr = Field(min_length=6, max_length=16)  # 6 digits, or a backup code 'xxxx-xxxx'


class Reauth(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=256)


class PasswordChange(BaseModel):
    current_password: SecretStr = Field(min_length=1, max_length=256)
    new_password: SecretStr = Field(min_length=1, max_length=256)


def _auth_time(svc: Svc, request: Request) -> datetime:
    """When the password behind this request's (already validated) token was typed."""
    secret = svc.settings.jwt_secret
    if secret is None:
        raise AuthError("server has no JWT secret")
    return token_auth_time(request.headers["authorization"][7:], secret.get_secret_value())


def _user(svc: Svc, user_id: str) -> UserRow:
    with transaction(svc.engine) as s:
        user = reads.get_user(s, user_id)
    if user is None:
        raise AuthError("user no longer active")
    return user


def _limited(request: Request, *key: str) -> None:
    limiter = request.app.state.login_limiter
    if not limiter.test(LOGIN_FAILURES, *key) or not limiter.test(HOURLY_FAILURES, *key):
        raise ProblemError(
            429, "too many failed attempts; try again later", ApiErrorCode.RATE_LIMITED
        )


def _failed(svc: Svc, request: Request, user: UserRow | None, reason: str, *key: str) -> None:
    limiter = request.app.state.login_limiter
    limiter.hit(LOGIN_FAILURES, *key)  # only failures count
    limiter.hit(HOURLY_FAILURES, *key)
    if user is not None:  # unknown usernames are not written to the audit chain
        svc.ledger.account_event(
            tenant_id=user.tenant_id,
            actor=user.id,
            event_type="LOGIN_FAILED",
            payload={"user_id": user.id, "username": user.username, "reason": reason},
        )


@router.post("/auth/token")
def token(body: Login, request: Request, svc: Svc) -> dict[str, Any]:
    key = (body.username.lower(), request.client.host if request.client else "unknown")
    _limited(request, *key)
    spray = (f"user:{body.username.lower()}",)  # all IPs together
    if not request.app.state.login_limiter.test(USERNAME_FAILURES, *spray):
        raise ProblemError(
            429, "too many failed attempts; try again later", ApiErrorCode.RATE_LIMITED
        )
    with transaction(svc.engine) as s:
        user = reads.user_by_name(s, body.username)
    digest = user.password_hash if user is not None else _DUMMY_HASH
    ok = verify_password(digest, body.password)
    if user is None or not ok or not user.active:
        request.app.state.login_limiter.hit(USERNAME_FAILURES, *spray)
        _failed(svc, request, user if user and user.active else None, "password", *key)
        raise AuthError("invalid credentials")
    if needs_rehash(user.password_hash):
        svc.ledger.set_password_hash(user.id, hash_password(body.password))
    return accounts.token_for(svc, user, mfa_done=False)


@router.post("/auth/mfa/verify")
def verify_mfa(body: Code, who: MfaPending, request: Request, svc: Svc) -> dict[str, Any]:
    """The second factor after a correct password: a TOTP code or one backup code."""
    key = (f"mfa:{who.user_id}",)  # per user: a stolen stage token cannot rotate IPs
    _limited(request, *key)
    user = _user(svc, who.user_id)
    if not accounts.check_second_factor(svc, user, body.code.get_secret_value(), actor=user.id):
        _failed(svc, request, user, "second_factor", *key)
        raise AuthError("invalid code")
    started = _auth_time(svc, request)
    return accounts.token_for(svc, _user(svc, who.user_id), mfa_done=True, auth_time=started)


@router.post("/auth/password")
def change_password(
    body: PasswordChange, who: SetupUser, request: Request, svc: Svc
) -> dict[str, Any]:
    """Change your own password: the current one, then the policy. Every other token is revoked."""
    key = (f"password:{who.user_id}",)
    _limited(request, *key)
    user = _user(svc, who.user_id)
    current = body.current_password.get_secret_value()
    new = body.new_password.get_secret_value()
    if not verify_password(user.password_hash, current):
        _failed(svc, request, user, "password_change", *key)
        raise ProblemError(403, "current password is not correct", ApiErrorCode.FORBIDDEN)
    found = password_policy.problems(new, user.username, current=current)
    if found:
        raise ProblemError(
            422,
            "choose another password: " + "; ".join(found),
            errors=[{"field": "new_password", "row": None, "reason": r} for r in found],
        )
    svc.ledger.update_user(
        user.id,
        tenant_id=user.tenant_id,
        actor=user.id,
        changes={
            "password_hash": hash_password(new),
            "must_change_password": False,  # nosec B105 - a flag name, not a secret
        },
        event_type="PASSWORD_CHANGED",
        revoke=True,
    )
    return accounts.token_for(svc, _user(svc, who.user_id), mfa_done=who.mfa)


@router.post("/auth/mfa/setup")
def start_mfa(body: Reauth, who: SetupUser, request: Request, svc: Svc) -> dict[str, Any]:
    """Start enrolment: a new secret for the authenticator app (shown once, stored sealed). Needs
    the password again, so a stolen token alone cannot bind the attacker's app to the account."""
    key = (f"password:{who.user_id}",)
    _limited(request, *key)
    user = _user(svc, who.user_id)
    if not verify_password(user.password_hash, body.current_password.get_secret_value()):
        _failed(svc, request, user, "mfa_setup", *key)
        raise ProblemError(403, "current password is not correct", ApiErrorCode.FORBIDDEN)
    if user.mfa_enabled:
        raise ProblemError(
            409, "a second factor is already set up; ask an administrator to reset it"
        )
    secret = mfa.new_secret()
    sealed = mfa.seal(accounts.mfa_key(svc), user.id, secret)
    svc.ledger.update_user(  # pending until enabled; not an account event yet
        user.id,
        tenant_id=user.tenant_id,
        actor=user.id,
        changes={"mfa_secret": sealed, "mfa_last_step": None},
    )
    return {"secret": secret, "otpauth_uri": mfa.provisioning_uri(secret, user.username)}


@router.post("/auth/mfa/enable")
def enable_mfa(body: Code, who: SetupUser, request: Request, svc: Svc) -> dict[str, Any]:
    """Finish enrolment with a code from the app; returns 8 backup codes (shown once) and the next
    token. Revokes every other token."""
    key = (f"mfa:{who.user_id}",)
    _limited(request, *key)
    user = _user(svc, who.user_id)
    if user.mfa_enabled or not user.mfa_secret:
        raise ProblemError(409, "start the setup first", ApiErrorCode.CONFLICT)
    secret = accounts.unseal(svc, user)
    step = mfa.verify_totp(secret, body.code.get_secret_value(), time.time(), None)
    if step is None:
        _failed(svc, request, user, "mfa_enrolment", *key)
        raise ProblemError(422, "that code is not valid; check the time on your phone")
    codes, hashes = mfa.new_backup_codes()
    svc.ledger.update_user(
        user.id,
        tenant_id=user.tenant_id,
        actor=user.id,
        changes={"mfa_enabled": True, "mfa_last_step": step, "mfa_backup": hashes},
        event_type="MFA_ENROLLED",
        revoke=True,
    )
    started = _auth_time(svc, request)  # enrolment never restarts the session clock
    return {"backup_codes": codes} | accounts.token_for(
        svc, _user(svc, who.user_id), mfa_done=True, auth_time=started
    )


@router.post("/auth/logout")
def logout(who: SetupUser, svc: Svc) -> dict[str, Any]:
    """Sign out everywhere: every token this user holds stops working at once."""
    svc.ledger.update_user(
        who.user_id,
        tenant_id=who.tenant_id,
        actor=who.user_id,
        changes={},
        event_type="SIGNED_OUT",
        revoke=True,
    )
    return {"signed_out": True}


@router.post("/auth/refresh")
def refresh(
    who: Account,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    svc: Svc,
) -> dict[str, Any]:
    """H12: swap a still-valid token for a fresh one. The user row was re-checked by `Account`
    (deactivated or revoked users are refused). The session ends JWT_SESSION_MAX_MINUTES after the
    password was typed; a refresh never extends that, so a stolen token cannot live forever."""
    secret = svc.settings.jwt_secret
    if secret is None:
        raise AuthError("server has no JWT secret")
    if creds is None:  # `Account` already refused a missing token; this keeps mypy and readers sure
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
        "stage": who.stage.value,
        "next": [],
    }


@router.get("/me")
def me(who: SetupUser, svc: Svc) -> dict[str, Any]:
    user = _user(svc, who.user_id)
    return {
        "user_id": who.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "role": who.role.value,
        "stage": who.stage.value,
        "must_change_password": user.must_change_password,
        "mfa_enabled": user.mfa_enabled,
        "mfa_required": svc.settings.mfa_required_for(user.role),
    }


@router.get("/me/chat-notice")
def chat_notice(who: User, svc: Svc) -> dict[str, Any]:
    """Scope #40: the copilot first-use notice and whether this user acknowledged this version."""
    return notice_state(svc, who)


@router.post("/me/chat-notice/ack")
def ack_chat_notice(who: User, svc: Svc) -> dict[str, Any]:
    """Scope #40: store the acknowledgement (once per user and notice version, audited)."""
    return acknowledge_notice(svc, who)
