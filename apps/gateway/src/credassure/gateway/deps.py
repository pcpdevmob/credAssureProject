"""Request dependencies: services, authentication, case scoping (NFR-07, SUP-08, scope #27).

The token only names the user; the user row is re-loaded on every request, so a deactivated
user or a changed role stops working at once (Phase 5 SHOULD). A case the caller may not see
answers 404, never 403, so its existence does not leak (BR-14).
"""

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Engine

from credassure.agents.supervisor.graph import Supervisor
from credassure.core.errors import ApiErrorCode
from credassure.core.ports import LLMPort
from credassure.gateway.problems import ProblemError
from credassure.gateway.settings import Settings
from credassure.ledger import reads
from credassure.ledger.models import Case
from credassure.ledger.session import transaction
from credassure.ledger.store import SqlLedger
from credassure.security.auth import (
    AuthError,
    CaseRef,
    Principal,
    Role,
    can_view_case,
    verify_token,
)


@dataclass
class Services:
    settings: Settings
    engine: Engine
    ledger: SqlLedger
    supervisor: Supervisor
    llm: LLMPort | None
    jobs: Any  # gateway.jobs.JobRunner (typed loosely to avoid an import cycle)
    service: Any = None  # gateway.supervisor_service.SupervisorService, set after construction


def services(request: Request) -> Services:
    svc: Services = request.app.state.services
    return svc


Svc = Annotated[Services, Depends(services)]
_bearer = HTTPBearer(auto_error=False)


def principal_from_token(svc: Services, token: str) -> Principal:
    secret = svc.settings.jwt_secret
    if secret is None:
        raise AuthError("server has no JWT secret")
    who = verify_token(token, secret.get_secret_value())
    with transaction(svc.engine) as s:
        user = reads.get_user(s, who.user_id)
        if (
            user is None
            or not user.active
            or user.role != who.role.value
            or user.tenant_id != who.tenant_id
        ):
            raise AuthError("user no longer active")
    return who


def current_user(
    svc: Svc, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> Principal:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AuthError("missing bearer token")
    return principal_from_token(svc, creds.credentials)


User = Annotated[Principal, Depends(current_user)]


def role(*roles: Role) -> Any:
    """Dependency: authorise the role before FastAPI validates the body (403 beats 422)."""

    def check(who: User) -> Principal:
        require(who, *roles)
        return who

    return Depends(check)


def require(who: Principal, *roles: Role) -> None:
    if who.role not in roles:
        raise ProblemError(403, f"role {who.role.value} may not do this", ApiErrorCode.FORBIDDEN)


def case_ref(case: Case) -> CaseRef:
    return CaseRef(case.id, case.tenant_id, case.preparer_id, case.route, case.status)


def visible_case(svc: Services, who: Principal, case_id: str) -> Case:
    """The case if this caller may see it (tenant + role + attribute policy), else 404."""
    with transaction(svc.engine) as s:
        case = reads.get_case(s, who.tenant_id, case_id)
    if case is None or not can_view_case(who, case_ref(case)):
        raise ProblemError(404, f"no case {case_id}", ApiErrorCode.NOT_FOUND)
    return case


def own_case(svc: Services, who: Principal, case_id: str) -> Case:
    """Only the preparer who owns the case may change its inputs or run it (BRD §5.1)."""
    case = visible_case(svc, who, case_id)
    if who.role is not Role.PREPARER or case.preparer_id != who.user_id:
        raise ProblemError(403, "only the case preparer may do this", ApiErrorCode.FORBIDDEN)
    return case
