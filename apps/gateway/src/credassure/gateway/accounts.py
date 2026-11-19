"""Sign-in stages, token issue and second-factor checks shared by the auth, users and workflow
routers (ADR 0038). The decisions are code; the routers only call these.

Stage order after a correct password: a user with MFA enrolled gives a code first (MFA); then a
temporary password must be changed and an approver or admin without MFA must enrol (SETUP); only
then is a FULL token issued. A stage token lives a few minutes and opens only its own routes.
"""

import time
from datetime import UTC, datetime
from typing import Any

from credassure.core.errors import ApiErrorCode
from credassure.gateway.deps import Services
from credassure.gateway.problems import ProblemError
from credassure.ledger import writes
from credassure.ledger.models import User as UserRow
from credassure.ledger.session import transaction
from credassure.security import mfa
from credassure.security.auth import AuthError, Principal, Role, Stage, issue_token

STAGE_MINUTES = {Stage.MFA: 5, Stage.SETUP: 10}


def stage_for(svc: Services, user: UserRow, *, mfa_done: bool) -> Stage:
    if user.mfa_enabled and not mfa_done:
        return Stage.MFA
    if user.must_change_password or needs_enrolment(svc, user):
        return Stage.SETUP
    return Stage.FULL


def needs_enrolment(svc: Services, user: UserRow) -> bool:
    return svc.settings.mfa_required_for(user.role) and not user.mfa_enabled


def next_steps(svc: Services, user: UserRow, stage: Stage) -> list[str]:
    if stage is Stage.MFA:
        return ["verify_mfa"]
    if stage is Stage.SETUP:
        return (["change_password"] if user.must_change_password else []) + (
            ["enrol_mfa"] if needs_enrolment(svc, user) else []
        )
    return []


def token_for(
    svc: Services, user: UserRow, *, mfa_done: bool, auth_time: datetime | None = None
) -> dict[str, Any]:
    """The token this user gets now, with the steps still due (empty when FULL)."""
    secret = svc.settings.jwt_secret
    if secret is None:
        raise AuthError("server has no JWT secret")
    stage = stage_for(svc, user, mfa_done=mfa_done)
    minutes = STAGE_MINUTES.get(stage, svc.settings.jwt_expiry_minutes)
    who = Principal(
        user.id, Role(user.role), user.tenant_id, stage, user.token_version or 0, mfa_done
    )
    return {
        "access_token": issue_token(who, secret.get_secret_value(), minutes, auth_time=auth_time),
        "token_type": "bearer",  # nosec B105 - OAuth2 token type name, not a secret
        "expires_in": minutes * 60,
        "stage": stage.value,
        "next": next_steps(svc, user, stage),
    }


def mfa_key(svc: Services) -> bytes:
    raw = svc.settings.mfa_encryption_key
    try:
        return mfa.load_key(raw.get_secret_value() if raw else None)
    except mfa.MfaError as exc:
        raise ProblemError(503, "second factor is not configured on this server") from exc


def check_second_factor(svc: Services, user: UserRow, code: str, *, actor: str) -> bool:
    """A TOTP code (newer than the last one used) or an unused backup code. On success the step or
    the spent backup code is stored, in the same transaction as its audit row."""
    if not user.mfa_enabled or not user.mfa_secret:
        return False
    secret = mfa.unseal(mfa_key(svc), user.id, user.mfa_secret)
    step = mfa.verify_totp(secret, code, time.time(), user.mfa_last_step)
    with transaction(svc.engine) as s:
        if step is not None:
            writes.update_user(
                s,
                user_id=user.id,
                tenant_id=user.tenant_id,
                actor=actor,
                changes={"mfa_last_step": step},
            )
            return True
        left = mfa.use_backup_code(list(user.mfa_backup or []), code) if "-" in code else None
        if left is None:
            return False
        writes.update_user(
            s,
            user_id=user.id,
            tenant_id=user.tenant_id,
            actor=actor,
            changes={"mfa_backup": left},
            event_type="BACKUP_CODE_USED",
        )
        return True


def now() -> datetime:
    return datetime.now(UTC)


def forbid(detail: str) -> ProblemError:
    return ProblemError(403, detail, ApiErrorCode.FORBIDDEN)
