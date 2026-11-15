"""Employee Onboarding agent, Gate 1 readiness (design-detail §2.4.2; ONB-01..06, BR-03/04).

Code decides: the HR profile comes from the case's preparer binding (ONB-01, never chat), the
rules engine sets every rule and the gate (ONB-02/03). The model only words the explanation of
failed rules (onb_explain) with {rule.<id>} slots that code renders; a draft that misses a failed
rule or has any figure outside a slot falls back to the template (ONB-04).
No tool writes HR data (ONB-05).
"""

import re
from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from credassure.agents.onboarding import __version__
from credassure.core import slots
from credassure.core.blockers import BlockerCode
from credassure.core.enums import AgentName, Decision
from credassure.core.errors import LLMError
from credassure.core.ports import LedgerPort, StageContext
from credassure.core.prompts import prompt_version
from credassure.core.prompts import registry as prompts
from credassure.core.results import AgentResult, Blocker, EvidenceRef
from credassure.engines.onboarding_rules import Readiness, evaluate

PROMPT = "onb_explain"
# VER-03 interim guard until the Critic (9d): no gate or approval wording from the model.
BANNED = re.compile(r"(?-i:\bGO\b|\bNO_GO\b)|approv|accept|\bsign", re.IGNORECASE)
ENGINE = "engines.onboarding_rules"
GATES = {"GO": Decision.GO, "NO_GO": Decision.NO_GO, "NEEDS_INPUT": Decision.NEEDS_INPUT}
RULE_NAMES = {
    "role": "authorised preparer role",
    "AML-201": "AML/KYC training (AML-201)",
    "DPDP-101": "Data Protection training (DPDP-101)",
    "FIN-101": "Credit Policy training (FIN-101)",
    "policy_ack": "working-capital policy acknowledgement (WC-POL v3)",
}
TEXT: dict[BlockerCode, tuple[str, str]] = {  # message, next action
    BlockerCode.ONB_ROLE_NOT_AUTHORISED: (
        "Your HR role is not authorised to prepare loan proposals.",
        "Ask a credit proposal officer or senior finance analyst to prepare this case.",
    ),
    BlockerCode.ONB_TRAINING_EXPIRED: (
        "This mandatory training has expired.",
        "Retake the course and ask HR to update your training record.",
    ),
    BlockerCode.ONB_TRAINING_INCOMPLETE: (
        "This mandatory training is not completed.",
        "Finish the course; HR records the completion.",
    ),
    BlockerCode.ONB_TRAINING_MISSING: (
        "HR has no record of this mandatory training.",
        "Ask HR to add your completion record, or enrol in the course.",
    ),
    BlockerCode.ONB_ACK_MISSING: (
        "You have not acknowledged the working-capital policy.",
        "Read and acknowledge WC-POL v3 in the HR portal.",
    ),
    BlockerCode.ONB_ACK_OLD_VERSION: (
        "You acknowledged an older version of the working-capital policy.",
        "Read and acknowledge the current version, WC-POL v3.",
    ),
}
GO_TEXT = (
    "Preparer readiness confirmed: authorised role, mandatory trainings current,"
    " WC-POL v3 acknowledged."
)


def version() -> str:
    return __version__


def _blockers(readiness: Readiness) -> list[Blocker]:
    out = []
    for rule, code in readiness.blockers:
        message, action = TEXT[code]
        out.append(
            Blocker(
                code=code,
                message=f"{RULE_NAMES[rule]} [{rule}]: {message}",
                field=rule,
                next_action=action,
            )
        )
    return out


def template(blockers: list[Blocker]) -> str:
    if not blockers:
        return GO_TEXT
    lines = [f"- {b.message} Next: {b.next_action}" for b in blockers]
    return "Preparer readiness is blocked:\n" + "\n".join(lines)


def narrative_slots(blockers: list[Blocker]) -> dict[str, str]:
    """ONB-04: failed rules only; a passed rule has no slot, so naming one rejects the draft."""
    out: dict[str, str] = {}
    for b in blockers:
        out[f"rule.{b.field}"] = RULE_NAMES.get(str(b.field), str(b.field))
        action = str(b.next_action or "").rstrip(".")
        out[f"next.{b.field}"] = action[:1].lower() + action[1:]
    return out


def _explain(ctx: StageContext, readiness: Readiness, blockers: list[Blocker]) -> str | None:
    """Model wording with {rule.<id>} / {next.<id>} slots, or None to use the template (ONB-04)."""
    if ctx.llm is None or not blockers:
        return None
    failed = "\n".join(f"{{rule.{b.field}}}: {b.code.value}; {{next.{b.field}}}" for b in blockers)
    prompt = prompts()[PROMPT].render(blockers=failed)
    try:
        reply = ctx.llm.complete(prompt, name=PROMPT).strip()
    except LLMError:  # slow or down model: the gate is already decided, only wording is lost
        return None
    return slots.render(
        reply,
        narrative_slots(blockers),
        required=[f"rule.{rule}" for rule in readiness.failed],
        banned=BANNED,
    )


def run(ctx: StageContext) -> AgentResult:
    profile: Mapping[str, Any] | None = ctx.tools.call("get_hr_profile", ctx.case_id)
    steps = 1
    if profile is None:
        missing = Blocker(
            code=BlockerCode.ONB_TRAINING_MISSING,
            message="HR has no active record for the preparer of this case.",
            field="hr_profile",
            next_action="Ask HR to create your employee record.",
        )
        return _result(
            ctx,
            Decision.NEEDS_INPUT,
            [missing],
            [],
            template([missing]),
            steps,
            {},
            question="HR has no record for you; can HR confirm your employee record?",
        )
    readiness: Readiness = ctx.tools.call(
        "evaluate_onboarding_rules", ctx.case_id, {"profile": dict(profile)}
    )
    steps += 1
    blockers = _blockers(readiness)
    drafted = _explain(ctx, readiness, blockers)
    versions = {}
    if ctx.llm is not None and blockers:
        steps += 1
        versions[PROMPT] = prompt_version(PROMPT)
    # Facts after the model call: a ModelUnavailable retry (template path) writes them once.
    ref = f"hr.db:employees:{profile['emp_id']}"
    evidence = []
    for rule, outcome in sorted(readiness.rules.items()):
        key = f"onb.rule.{rule}"
        ctx.ledger.put_fact(
            ctx.case_id,
            key,
            outcome,
            unit="enum",
            source_type="hr_record",
            source_ref=ref,
            produced_by=ENGINE,
        )
        evidence.append(EvidenceRef(kind="ledger_fact", ref_id=key))
    ctx.ledger.put_fact(
        ctx.case_id,
        "onb.gate",
        readiness.gate,
        unit="enum",
        source_type="hr_record",
        source_ref=ref,
        produced_by=ENGINE,
    )
    evidence.append(EvidenceRef(kind="ledger_fact", ref_id="onb.gate"))
    unknown = [b for b in blockers if b.code is BlockerCode.ONB_TRAINING_MISSING]
    question = (
        f"HR has no record of {RULE_NAMES[str(unknown[0].field)]}; can HR add it?"
        if readiness.gate == "NEEDS_INPUT" and unknown
        else None
    )
    return _result(
        ctx,
        GATES[readiness.gate],
        blockers,
        evidence,
        drafted or template(blockers),
        steps,
        versions,
        question=question,
    )


def _result(
    ctx: StageContext,
    decision: Decision,
    blockers: list[Blocker],
    evidence: list[EvidenceRef],
    narrative: str,
    steps: int,
    versions: dict[str, str],
    *,
    question: str | None = None,
) -> AgentResult:
    return AgentResult(
        agent=AgentName.ONBOARDING,
        case_id=ctx.case_id,
        stage=ctx.stage,
        tenant_id=ctx.tenant_id,
        decision=decision,
        evidence=evidence,
        blockers=blockers,
        question=question,
        narrative=narrative,
        prompt_versions=versions,
        steps_used=steps,
        trace_id=ctx.trace_id,
        agent_version=__version__,
    )


def make_recheck(
    load_profile: Callable[[str], Mapping[str, Any] | None], as_of: date
) -> Callable[[AgentResult, LedgerPort], list[Blocker]]:
    """SUP-05: recompute readiness from hr.db on every GO; any disagreement overrides the agent."""

    def recheck(result: AgentResult, ledger: LedgerPort) -> list[Blocker]:
        profile = load_profile(result.case_id)
        if profile is None:
            return [
                Blocker(
                    code=BlockerCode.ONB_TRAINING_MISSING,
                    message="recheck: HR has no record for the preparer",
                )
            ]
        readiness = evaluate(profile, as_of)
        failed = _blockers(readiness)
        facts = {f"onb.rule.{r}": o for r, o in readiness.rules.items()} | {
            "onb.gate": readiness.gate
        }
        for key, want in sorted(facts.items()):
            got = ledger.get(result.case_id, key)
            if got != want:
                failed.append(
                    Blocker(
                        code=BlockerCode.SUP_RECHECK_MISMATCH,
                        message=f"recheck: ledger {key}={got}, recomputed {want}",
                    )
                )
        return failed

    return recheck
