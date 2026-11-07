"""Token quota monitor (scope #16, NFR-03): warnings at 70% and 90% of TOKEN_QUOTA."""

from typing import Any

from credassure.ledger import reads
from credassure.ledger.session import transaction

WARN_70, WARN_90 = 0.70, 0.90


def level(used: int, limit: int) -> str:
    ratio = used / limit
    if ratio >= 1:
        return "exhausted"
    if ratio >= WARN_90:
        return "warn_90"
    if ratio >= WARN_70:
        return "warn_70"
    return "ok"


def quota(svc: Any) -> dict[str, Any]:
    with transaction(svc.engine) as s:
        used = reads.tokens_used(s, svc.settings.tenant_id)
    limit = svc.settings.token_quota
    return {"used": used, "limit": limit, "level": level(used, limit)}
