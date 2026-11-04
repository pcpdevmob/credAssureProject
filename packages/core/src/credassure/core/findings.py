"""Critic finding contract (scope #21 schema). Regeneration is Phase 9d."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from credassure.core.blockers import BlockerCode
from credassure.core.enums import Stage


class FindingSeverity(StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"


class CriticFinding(BaseModel):
    """One critic result. ``critical`` blocks the gate; ``warning`` does not."""

    schema_version: Literal["1.0"] = "1.0"
    severity: FindingSeverity
    code: BlockerCode
    message: str
    span: str | None = None
    target_stage: Stage | None = None
