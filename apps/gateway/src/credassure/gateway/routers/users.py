"""User administration (ADR 0038): the user_admin role only, in its own tenant, every change
audited in the hash-chained log. POST for every change (the CORS allow-list is GET and POST).

Rules enforced here, in code:
- an admin cannot change their own role, disable themselves or reset their own second factor
  (use /v1/auth/password for your own password);
- the last active user_admin can be neither demoted nor disabled;
- a role change, disable, password reset or MFA reset revokes every token the user holds;
- a temporary password is returned once and must be changed at the next sign-in.
"""

import re
import secrets
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from credassure.core.errors import ApiErrorCode
from credassure.gateway.accounts import forbid
from credassure.gateway.deps import Svc, UserAdmin
from credassure.gateway.problems import ProblemError
from credassure.ledger import reads
from credassure.ledger.errors import ConflictError
from credassure.ledger.models import User as UserRow
from credassure.ledger.session import transaction
from credassure.security.auth import Principal, Role, hash_password

router = APIRouter(prefix="/v1/admin/users", tags=["users"])
USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
EMP_ID = re.compile(r"^E[0-9]{3,6}$")


class NewUser(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    role: Role
    emp_id: str | None = Field(default=None, max_length=16)  # preparers: the HR binding (ONB-01)

    @field_validator("username")
    @classmethod
    def _username(cls, value: str) -> str:
        if not USERNAME.match(value):
            raise ValueError("lower-case letters, digits, '.', '_' or '-'; 3-64 characters")
        return value

    @field_validator("emp_id")
    @classmethod
    def _emp(cls, value: str | None) -> str | None:
        if value is not None and not EMP_ID.match(value):
            raise ValueError("an HR id such as E001")
        return value


class RoleChange(BaseModel):
    role: Role


def view(user: UserRow) -> dict[str, Any]:
    """What an admin sees: never a hash, a sealed secret or a backup code."""
    return {
        "user_id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "emp_id": user.emp_id,
        "active": user.active,
        "must_change_password": user.must_change_password,
        "mfa_enabled": user.mfa_enabled,
        "backup_codes_left": len(user.mfa_backup or []),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def _temporary() -> str:
    return secrets.token_urlsafe(15)  # 20 characters, ~120 bits


def _change(
    svc: Svc,
    who: Principal,
    user_id: str,
    check: Callable[[Any, UserRow], None],
    **update: Any,
) -> UserRow:
    """One transaction (the ledger's): load the target in the admin's tenant, run the rule
    check, write."""
    try:
        return svc.ledger.update_user(
            user_id, tenant_id=who.tenant_id, actor=who.user_id, check=check, **update
        )
    except ConflictError as exc:
        raise ProblemError(404, f"no user {user_id}", ApiErrorCode.NOT_FOUND) from exc


def _not_self(who: Principal, user_id: str, what: str) -> None:
    if user_id == who.user_id:
        raise forbid(f"you cannot {what} your own account")


def _keeps_an_admin(s: Any, user: UserRow, tenant_id: str) -> None:
    if (
        user.role == Role.USER_ADMIN.value
        and user.active
        and reads.active_admins(s, tenant_id) <= 1
    ):
        raise ProblemError(409, "this is the last active user_admin", ApiErrorCode.CONFLICT)


@router.get("")
def list_users(who: UserAdmin, svc: Svc) -> list[dict[str, Any]]:
    with transaction(svc.engine) as s:
        return [view(u) for u in reads.list_users(s, who.tenant_id)]


@router.post("", status_code=201)
def create_user(body: NewUser, who: UserAdmin, svc: Svc) -> dict[str, Any]:
    if body.emp_id is not None and body.role is not Role.PREPARER:
        raise ProblemError(
            422,
            "only a preparer is bound to an HR id",
            errors=[{"field": "emp_id", "row": None, "reason": "preparers only"}],
        )
    temporary = _temporary()
    try:
        user = svc.ledger.create_user(
            tenant_id=who.tenant_id,
            actor=who.user_id,
            username=body.username,
            role=body.role.value,
            password_hash=hash_password(temporary),
            display_name=body.display_name,
            emp_id=body.emp_id,
        )
        out = view(user)
    except ConflictError as exc:
        raise ProblemError(409, str(exc), ApiErrorCode.CONFLICT) from exc
    return {"user": out, "temporary_password": temporary}


@router.post("/{user_id}/role")
def change_role(user_id: str, body: RoleChange, who: UserAdmin, svc: Svc) -> dict[str, Any]:
    _not_self(who, user_id, "change the role of")  # an HR binding stays; read for preparers only

    def check(s: Any, user: UserRow) -> None:
        if body.role.value != user.role:
            _keeps_an_admin(s, user, who.tenant_id)

    user = _change(
        svc,
        who,
        user_id,
        check,
        changes={"role": body.role.value},
        event_type="USER_ROLE_CHANGED",
        payload={"role": body.role.value, "by": who.user_id},
        revoke=True,
    )
    return view(user)


@router.post("/{user_id}/disable")
def disable(user_id: str, who: UserAdmin, svc: Svc) -> dict[str, Any]:
    _not_self(who, user_id, "disable")
    user = _change(
        svc,
        who,
        user_id,
        lambda s, u: _keeps_an_admin(s, u, who.tenant_id),
        changes={"active": False},
        event_type="USER_DISABLED",
        payload={"by": who.user_id},
        revoke=True,
    )
    return view(user)


@router.post("/{user_id}/enable")
def enable(user_id: str, who: UserAdmin, svc: Svc) -> dict[str, Any]:
    user = _change(
        svc,
        who,
        user_id,
        lambda s, u: None,
        changes={"active": True},
        event_type="USER_ENABLED",
        payload={"by": who.user_id},
    )
    return view(user)


@router.post("/{user_id}/reset-password")
def reset_password(user_id: str, who: UserAdmin, svc: Svc) -> dict[str, Any]:
    _not_self(who, user_id, "reset the password of")
    temporary = _temporary()
    user = _change(
        svc,
        who,
        user_id,
        lambda s, u: None,
        changes={
            "password_hash": hash_password(temporary),
            "must_change_password": True,  # nosec B105 - a flag name, not a secret
        },
        event_type="PASSWORD_RESET",
        payload={"by": who.user_id},
        revoke=True,
    )
    return {"user": view(user), "temporary_password": temporary}


@router.post("/{user_id}/reset-mfa")
def reset_mfa(user_id: str, who: UserAdmin, svc: Svc) -> dict[str, Any]:
    _not_self(who, user_id, "reset the second factor of")
    user = _change(
        svc,
        who,
        user_id,
        lambda s, u: None,
        changes={
            "mfa_enabled": False,
            "mfa_secret": None,  # nosec B105 - clearing the sealed secret, not a value
            "mfa_last_step": None,
            "mfa_backup": None,
        },
        event_type="MFA_RESET",
        payload={"by": who.user_id},
        revoke=True,
    )
    return view(user)


@router.get("/events")
def events(who: UserAdmin, svc: Svc, limit: int = 200) -> list[dict[str, Any]]:
    with transaction(svc.engine) as s:
        rows = reads.account_events(s, who.tenant_id, max(1, min(limit, 500)))
        return [
            {
                "seq": e.seq,
                "ts": e.ts,
                "actor": e.actor,
                "event_type": e.event_type,
                "payload": e.payload,
            }
            for e in rows
        ]
