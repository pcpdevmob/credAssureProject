"""Placeholder stage agent (ONB-01): returns a real AgentResult through the contract.

The Supervisor decides what happens next; this placeholder always reports GO. The model, when
enabled, only drafts the narrative (BR-05). Replaced by the real agent in its Phase 9 step.
"""

from credassure.agents.onboarding import __version__
from credassure.core.enums import AgentName, Decision
from credassure.core.ports import StageContext
from credassure.core.results import AgentResult, EvidenceRef

TEMPLATE = "Preparer readiness confirmed (placeholder until Phase 9a)."


def version() -> str:
    return __version__


def run(ctx: StageContext) -> AgentResult:
    evidence: list[EvidenceRef] = []
    narrative = TEMPLATE if ctx.llm is None else ctx.llm.complete(TEMPLATE, name="onb_explain")
    return AgentResult(
        agent=AgentName.ONBOARDING,
        case_id=ctx.case_id,
        stage=ctx.stage,
        tenant_id=ctx.tenant_id,
        decision=Decision.GO,
        evidence=evidence,
        narrative=narrative,
        prompt_versions={} if ctx.llm is None else {"onb_explain": "placeholder"},
        steps_used=1,
        trace_id=ctx.trace_id,
        agent_version=__version__,
    )
