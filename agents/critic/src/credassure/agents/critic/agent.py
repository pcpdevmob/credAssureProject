"""Placeholder stage agent (VER-01): returns a real AgentResult through the contract.

The Supervisor decides what happens next; this placeholder always reports GO. The model, when
enabled, only drafts the narrative (BR-05). Replaced by the real agent in its Phase 9 step.
"""

from credassure.agents.critic import __version__
from credassure.core.enums import AgentName, Decision
from credassure.core.ports import StageContext
from credassure.core.results import AgentResult, EvidenceRef

TEMPLATE = "No findings (placeholder until Phase 9d)."


def version() -> str:
    return __version__


def run(ctx: StageContext) -> AgentResult:
    evidence: list[EvidenceRef] = []
    narrative = TEMPLATE if ctx.llm is None else ctx.llm.complete(TEMPLATE, name="ver_note")
    return AgentResult(
        agent=AgentName.CRITIC,
        case_id=ctx.case_id,
        stage=ctx.stage,
        tenant_id=ctx.tenant_id,
        decision=Decision.GO,
        evidence=evidence,
        narrative=narrative,
        prompt_versions={} if ctx.llm is None else {"ver_note": "placeholder"},
        steps_used=1,
        trace_id=ctx.trace_id,
        agent_version=__version__,
    )
