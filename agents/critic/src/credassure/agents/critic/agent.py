"""Verification Critic stage, Gate 4 (VER-01..05, design-detail §2.4.5).

The model does not check itself: this stage uses no model. It re-verifies every upstream narrative
(``onb.narrative``, ``wc.narrative``, ``lw.narrative``) and the negotiation message against the
case's *current* ledger through the ``verify_claims`` tool, so a narrative that went stale or was
altered after its stage ran is caught here. Zero critical findings → GO; otherwise NO_GO with the
findings written to ``ver.findings`` so the Supervisor re-routes to the owning stage (ARCHITECTURE
§6.3). Under ablation A2 the Critic is off and the stage passes.
"""

import json
from typing import Any

from credassure.agents.critic import __version__
from credassure.core.enums import AgentName, Decision, Stage
from credassure.core.findings import CriticFinding, FindingSeverity
from credassure.core.narrative import parse
from credassure.core.ports import StageContext
from credassure.core.results import AgentResult, Blocker, EvidenceRef

NARRATIVES = {
    "onb.narrative": Stage.ONBOARDING,
    "wc.narrative": Stage.WORKING_CAPITAL,
    "lw.narrative": Stage.LENDWISE,
}
NEGOTIATION = "lw.negotiation."
FINDINGS_KEY = "ver.findings"


def version() -> str:
    return __version__


def _texts(ctx: StageContext) -> list[tuple[str, Stage | None, dict[str, Any]]]:
    out: list[tuple[str, Stage | None, dict[str, Any]]] = []
    for key, stage in NARRATIVES.items():
        stored = parse(ctx.ledger.get(ctx.case_id, key))
        if stored is None:
            continue
        text, model, slots = stored
        out.append((key, stage, {"text": text, "slots": slots, "model": model}))
    if ctx.ledger.get(ctx.case_id, NEGOTIATION + "status") == "sent":
        message = ctx.ledger.get(ctx.case_id, NEGOTIATION + "message") or ""
        keys = [NEGOTIATION + "current_fee", NEGOTIATION + "competing_fee"]
        # stage None: re-running LendWise cannot rewrite a sent message, so its findings pause the
        # case instead of re-routing (they cannot be fixed by a stage re-run).
        out.append((NEGOTIATION + "message", None, {"text": message, "keys": keys}))
    return out


def run(ctx: StageContext) -> AgentResult:
    checked: list[str] = []
    findings: list[CriticFinding] = []
    steps = 0
    if ctx.ablation != "A2":
        for key, stage, args in _texts(ctx):
            found: list[CriticFinding] = ctx.tools.call(
                "verify_claims", ctx.case_id, {**args, "stage": stage.value if stage else None}
            )
            steps += 1
            checked.append(key)
            findings += [f for f in found if f.severity is FindingSeverity.CRITICAL]
    ctx.ledger.put_fact(
        ctx.case_id,
        FINDINGS_KEY,
        json.dumps([f.model_dump(mode="json") for f in findings], sort_keys=True),
        unit="json",
        source_type="critic",
        source_ref=",".join(checked) or "none",
        produced_by=f"agents.critic@{__version__}",
    )
    blockers = [
        Blocker(
            code=f.code,
            message=f.message,
            field=f.target_stage.value if f.target_stage else None,  # the stage to fix
        )
        for f in findings
    ]
    if ctx.ablation == "A2":
        note = "Verification is switched off (ablation A2)."
    elif findings:
        note = "Verification found claims that are not supported; the owning stage is reopened."
    else:
        note = "Every figure, reason and citation checked matches the ledger and its sources."
    return AgentResult(
        agent=AgentName.CRITIC,
        case_id=ctx.case_id,
        stage=ctx.stage,
        tenant_id=ctx.tenant_id,
        decision=Decision.NO_GO if findings else Decision.GO,
        evidence=[EvidenceRef(kind="ledger_fact", ref_id=k) for k in [*checked, FINDINGS_KEY]],
        blockers=blockers,
        output_ref=FINDINGS_KEY,
        narrative=note,
        steps_used=max(steps, 1),
        trace_id=ctx.trace_id,
        agent_version=__version__,
    )
