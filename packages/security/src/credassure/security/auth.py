"""Identity and authorisation policy (NFR-07, SUP-08, BR-14, APR-05). Pure functions.

One policy module (ARCHITECTURE §8.5): role + attribute checks on tenant, case ownership and the
routed approver, with maker-checker (whoever prepared a case never decides it). The gateway wires
these into FastAPI dependencies (Phase 8).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

ALGORITHM = "HS256"
MIN_SECRET = 32
MAX_MINUTES = 60
ISSUER = AUDIENCE = "credassure"
DECIDABLE = frozenset({"AWAITING_APPROVAL", "HELD"})  # only these case statuses take a decision
_HASHER = PasswordHasher()  # argon2id, library defaults (RFC 9106 low-memory profile)


class Role(StrEnum):
    PREPARER = "preparer"
    DIRECTOR_FINANCE = "director_finance"
    VP_FINANCE = "vp_finance"
    EVALUATOR = "evaluator"


class AuthError(Exception):
    """Token or credential is not valid (HTTP 401)."""


class ForbiddenError(Exception):
    """Authenticated, but this role or attribute may not do this (HTTP 403)."""


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: Role
    tenant_id: str


@dataclass(frozen=True)
class CaseRef:
    """The attributes the policy needs; route is the engine's Route or None before routing."""

    case_id: str
    tenant_id: str
    preparer_id: str
    route: str | None
    status: str


# Routed states each approver handles; HELD (exactly ₹1.5 cr, rule hold) goes to the VP (BRD §5.1).
APPROVER_ROUTES: dict[Role, frozenset[str]] = {
    Role.DIRECTOR_FINANCE: frozenset({"director_finance"}),
    Role.VP_FINANCE: frozenset({"vp_finance", "HELD"}),
}

_ROUTES_BY_NAME = {r.value: routes for r, routes in APPROVER_ROUTES.items()}


def may_decide_route(role: str, route: str | None) -> bool:
    """Shared with the ledger so the write path applies the same route → role rule."""
    return route in _ROUTES_BY_NAME.get(role, frozenset())


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def needs_rehash(digest: str) -> bool:
    """True when the stored hash predates the current argon2 parameters (rehash on login)."""
    try:
        return _HASHER.check_needs_rehash(digest)
    except InvalidHashError:
        return True


def verify_password(digest: str, password: str) -> bool:
    try:
        return _HASHER.verify(digest, password)
    except (VerificationError, InvalidHashError):
        return False


def issue_token(who: Principal, secret: str, minutes: int, now: datetime | None = None) -> str:
    if len(secret) < MIN_SECRET:
        raise AuthError("JWT secret too short")
    if not 0 < minutes <= MAX_MINUTES:
        raise AuthError(f"token lifetime must be 1..{MAX_MINUTES} minutes")
    now = now or datetime.now(UTC)
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": who.user_id,
        "role": who.role.value,
        "tenant": who.tenant_id,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def verify_token(token: str, secret: str, now: datetime | None = None) -> Principal:
    if len(secret) < MIN_SECRET:
        raise AuthError("JWT secret too short")
    now = now or datetime.now(UTC)
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],  # never "none", never a header-chosen algorithm
            issuer=ISSUER,
            audience=AUDIENCE,
            # exp is checked below against the injected clock, so tests and replay are deterministic
            options={
                "require": ["iss", "aud", "sub", "role", "tenant", "exp"],
                "verify_exp": False,
                "verify_iat": False,
            },
        )
        if datetime.fromtimestamp(claims["exp"], UTC) <= now:
            raise AuthError("token expired")
        return Principal(str(claims["sub"]), Role(claims["role"]), str(claims["tenant"]))
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise AuthError("invalid token") from exc


def require_role(who: Principal, *roles: Role) -> None:
    if who.role not in roles:
        raise ForbiddenError(f"role {who.role} may not do this")


def can_view_case(who: Principal, case: CaseRef) -> bool:
    if who.tenant_id != case.tenant_id:
        return False
    if who.role is Role.EVALUATOR:
        return True
    if who.role is Role.PREPARER:
        return who.user_id == case.preparer_id
    return who.role in APPROVER_ROUTES and case.route in APPROVER_ROUTES[who.role]


def can_decide(who: Principal, case: CaseRef) -> bool:
    """Routed approver role only, same tenant, never whoever prepared the case (maker-checker)."""
    return (
        who.tenant_id == case.tenant_id
        and who.user_id != case.preparer_id
        and case.status in DECIDABLE
        and may_decide_route(who.role, case.route)
    )
