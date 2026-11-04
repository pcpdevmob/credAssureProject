"""AgentResult placeholder (design-detail §2.1). Freeze waits for approval after Phase 1.

`agent_version` (scope #25) and `tenant_id` (scope #27) are on the model so Phase 1 does not
change the shape. They are not frozen until that approval.
"""

from typing import Literal

from pydantic import BaseModel, Field

from credassure.core.enums import AgentName, Decision, Stage


class EvidenceRef(BaseModel):
    kind: Literal["ledger_fact", "passage", "hr_record", "offer_version", "file"]
    ref_id: str
    note: str | None = None


class Blocker(BaseModel):
    code: str
    message: str
    field: str | None = None
    next_action: str | None = None


class AgentResult(BaseModel):
    """What one agent invocation returns. `decision` is filled by code, never by the model."""

    agent: AgentName
    case_id: str
    stage: Stage
    tenant_id: str = "default"
    decision: Decision
    evidence: list[EvidenceRef] = Field(default_factory=list)
    blockers: list[Blocker] = Field(default_factory=list)
    question: str | None = None
    output_ref: str | None = None
    narrative: str | None = None
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    steps_used: int = 0
    tokens_used: int = 0
    trace_id: str
    agent_version: str
