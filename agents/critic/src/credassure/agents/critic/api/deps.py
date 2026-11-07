"""Dependencies the gateway overrides (ADR 0005): the Supervisor service and the caller.

Defaults fail closed: an unwired router answers 401 / raises, it never runs an agent directly.
"""

from typing import Any

from fastapi import HTTPException

from credassure.core.ports import SupervisorPort, UnavailableSupervisor


def get_supervisor() -> SupervisorPort:
    return UnavailableSupervisor()


def get_principal() -> Any:
    raise HTTPException(status_code=401, detail="not authenticated")
