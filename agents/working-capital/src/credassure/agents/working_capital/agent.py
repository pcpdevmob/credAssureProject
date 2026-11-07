"""Placeholder stage agent (WC-01): returns a real AgentResult through the contract.

The Supervisor decides what happens next; this placeholder always reports GO. The model, when
enabled, only drafts the narrative (BR-05). Replaced by the real agent in its Phase 9 step.
"""

from decimal import Decimal

from credassure.agents.working_capital import __version__
from credassure.core.enums import AgentName, Decision
from credassure.core.ports import StageContext
from credassure.core.results import AgentResult, EvidenceRef

TEMPLATE = "Funding need placeholder ₹1,42,00,000 (Phase 9b computes it)."

# ponytail: the demo case need (Appendix A); Phase 9b replaces it with engines.cashflow.
PLACEHOLDER_NEED = Decimal("14200000")


def version() -> str:
    return __version__


def run(ctx: StageContext) -> AgentResult:
    key = "wc.recommended_amount"
    ctx.ledger.put_fact(
        ctx.case_id,
        key,
        PLACEHOLDER_NEED,
        unit="INR",
        source_type="placeholder",
        source_ref="agents.working_capital.placeholder",
        produced_by=f"working_capital@{__version__}",
    )
    evidence = [EvidenceRef(kind="ledger_fact", ref_id=key)]
    narrative = TEMPLATE if ctx.llm is None else ctx.llm.complete(TEMPLATE, name="wc_explain")
    return AgentResult(
        agent=AgentName.WORKING_CAPITAL,
        case_id=ctx.case_id,
        stage=ctx.stage,
        tenant_id=ctx.tenant_id,
        decision=Decision.GO,
        evidence=evidence,
        narrative=narrative,
        prompt_versions={} if ctx.llm is None else {"wc_explain": "placeholder"},
        steps_used=1,
        trace_id=ctx.trace_id,
        agent_version=__version__,
    )
