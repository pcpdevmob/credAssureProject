"""Placeholder stage agent (LW-01): returns a real AgentResult through the contract.

The Supervisor decides what happens next; this placeholder always reports GO. The model, when
enabled, only drafts the narrative (BR-05). Replaced by the real agent in its Phase 9 step.
"""

from credassure.agents.lendwise import __version__
from credassure.core.enums import AgentName, Decision
from credassure.core.ports import StageContext
from credassure.core.results import AgentResult, EvidenceRef

TEMPLATE = "Offer comparison placeholder (Phase 9c audits and ranks offers)."


def version() -> str:
    return __version__


def run(ctx: StageContext) -> AgentResult:
    evidence: list[EvidenceRef] = []
    narrative = TEMPLATE if ctx.llm is None else ctx.llm.complete(TEMPLATE, name="lw_explain")
    return AgentResult(
        agent=AgentName.LENDWISE,
        case_id=ctx.case_id,
        stage=ctx.stage,
        tenant_id=ctx.tenant_id,
        decision=Decision.GO,
        evidence=evidence,
        narrative=narrative,
        prompt_versions={} if ctx.llm is None else {"lw_explain": "placeholder"},
        steps_used=1,
        trace_id=ctx.trace_id,
        agent_version=__version__,
    )
