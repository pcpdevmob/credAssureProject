"""Employee Onboarding agent, Gate 1 readiness (design-detail §2.4.2; ONB-01..06, BR-03/04).

Code decides: the HR profile comes from the case's preparer binding (ONB-01, never chat), the
rules engine sets every rule and the gate (ONB-02/03). The agent's own checker (`checker.py`, a
separate implementation of the same rule book) runs beside it; any difference stops the stage with
ERROR, never GO (SUP-05, BR-11), and the Supervisor's re-check uses the checker. Every blocker says
who fixes it (you, your manager or HR) and what to do; each `onb.rule.<id>` fact cites the HR record
it was decided on. The model only words the explanation of failed rules (onb_explain) with
{rule.<id>} slots that code renders; a draft that misses a failed rule or has any figure outside a
slot falls back to the template (ONB-04). No tool writes HR data (ONB-05).
0.3.0: design from Mousita (PR #43).
"""

from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from credassure.agents.onboarding import __version__, checker
from credassure.agents.onboarding.rules import (
    BLOCKERS,
    NO_RECORD,
    RULE_NAMES,
    BlockerText,
    next_action,
    source_ref,
)
from credassure.core import narrative, slots
from credassure.core.blockers import BlockerCode
from credassure.core.enums import AgentName, Decision
from credassure.core.ports import LedgerPort, StageContext
from credassure.core.prompts import prompt_version
from credassure.core.prompts import registry as prompts
from credassure.core.results import AgentResult, Blocker, EvidenceRef
from credassure.engines.onboarding_rules import Readiness

PROMPT = "onb_explain"
ENGINE = "engines.onboarding_rules"
GATES = {"GO": Decision.GO, "NO_GO": Decision.NO_GO, "NEEDS_INPUT": Decision.NEEDS_INPUT}
GO_TEXT = (
    "Preparer readiness confirmed: your role is authorised to prepare loan proposals, your"
    " mandatory trainings are current and you have acknowledged the current working-capital policy."
)
BLOCKED = "Preparer readiness is blocked. Each item says who fixes it and what to do:"
CLOSING = "When the HR records are updated, run the preparer check again."
MISMATCH = (
    "Preparer readiness could not be confirmed: two separate checks of the same HR record gave"
    " different results, so the case stops here."
)


def version() -> str:
    return __version__


def _text(b: Blocker) -> BlockerText:
    return BLOCKERS.get(b.code, NO_RECORD)


def _blockers(found: tuple[tuple[str, BlockerCode], ...]) -> list[Blocker]:
    out = []
    for rule, code in found:
        text = BLOCKERS[code]
        out.append(
            Blocker(
                code=code,
                message=f"{RULE_NAMES[rule]} [{rule}]: {text.message}",
                field=rule,
                next_action=next_action(text),
            )
        )
    return out


def template(blockers: list[Blocker]) -> str:
    """The readiness message when the model is off or its draft fails: no figures of its own (the
    rule ids and the policy version are names), one line per blocker with who fixes it."""
    if not blockers:
        return GO_TEXT
    lines = [
        f"- {b.message} Who fixes it: {_text(b).who}. Next: {_text(b).action}" for b in blockers
    ]
    return "\n".join([BLOCKED, *lines, CLOSING])


def narrative_slots(blockers: list[Blocker]) -> dict[str, str]:
    """ONB-04: failed rules only; a passed rule has no slot, so naming one rejects the draft.
    The {next.<id>} slot is the action alone: the model's sentence carries no "who" line."""
    out: dict[str, str] = {}
    for b in blockers:
        out[f"rule.{b.field}"] = RULE_NAMES.get(str(b.field), str(b.field))
        action = _text(b).action.rstrip(".")
        out[f"next.{b.field}"] = action[:1].lower() + action[1:]
    return out


def _explain(
    ctx: StageContext, readiness: Readiness, blockers: list[Blocker]
) -> tuple[str | None, str | None]:
    """(model wording with {rule.<id>} / {next.<id>} slots or None for the template, prompt used).
    The Critic checks whatever is shown (VER-01/03); its findings come back as ctx.findings."""
    if not blockers:
        return None, None
    failed = "\n".join(f"{{rule.{b.field}}}: {b.code.value}; {{next.{b.field}}}" for b in blockers)
    reply, used = narrative.draft(ctx, PROMPT, prompts()[PROMPT].render(blockers=failed))
    if reply is None:
        return None, used
    rendered = slots.render(
        reply, narrative_slots(blockers), required=[f"rule.{rule}" for rule in readiness.failed]
    )
    return rendered, used


def run(ctx: StageContext) -> AgentResult:
    profile: Mapping[str, Any] | None = ctx.tools.call("get_hr_profile", ctx.case_id)
    steps = 1
    if profile is None:
        missing = Blocker(
            code=BlockerCode.ONB_TRAINING_MISSING,
            message=NO_RECORD.message,
            field="hr_profile",
            next_action=next_action(NO_RECORD),
        )
        text = "\n".join(
            [BLOCKED, f"- {NO_RECORD.message} Who fixes it: HR. Next: {NO_RECORD.action}"]
        )
        narrative.record(
            ctx,
            "onb.",
            text,
            model=False,
            slots={},
            source_ref="hr.db:employees:none",
            produced_by=f"agents.onboarding@{__version__}",
        )
        return _result(
            ctx,
            Decision.NEEDS_INPUT,
            [missing],
            [],
            text,
            steps,
            {},
            question="HR has no record for you; can HR confirm your employee record?",
        )
    readiness: Readiness = ctx.tools.call(
        "evaluate_onboarding_rules", ctx.case_id, {"profile": dict(profile)}
    )
    steps += 1
    own = checker.check(profile, ctx.clock.today())
    disagree = checker.differences(own, readiness.gate, readiness.rules, readiness.blockers)
    if disagree:
        return _mismatch(ctx, str(profile["emp_id"]), disagree, steps)
    blockers = _blockers(readiness.blockers)
    drafted, used = _explain(ctx, readiness, blockers)
    versions = {}
    if used is not None:
        steps += 1
        versions[used] = prompt_version(used)
    # Facts after the model call: a ModelUnavailable retry (template path) writes them once.
    emp_id = str(profile["emp_id"])
    ref = source_ref(emp_id, "role")
    evidence = []
    for rule, outcome in sorted(readiness.rules.items()):
        key = f"onb.rule.{rule}"
        ctx.ledger.put_fact(
            ctx.case_id,
            key,
            outcome,
            unit="enum",
            source_type="hr_record",
            source_ref=source_ref(emp_id, rule),  # the record this rule was decided on
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
    text = drafted or template(blockers)
    narrative.record(
        ctx,
        "onb.",
        text,
        model=drafted is not None,
        slots=narrative_slots(blockers),
        source_ref=ref,
        produced_by=f"agents.onboarding@{__version__}",
    )
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
        text,
        steps,
        versions,
        question=question,
    )


def _mismatch(ctx: StageContext, emp_id: str, disagree: list[str], steps: int) -> AgentResult:
    """The engine and the agent's checker differ: no rule fact and no gate is written, the stage
    ends in ERROR (state saved; an evaluator retries after the cause is fixed). Never GO."""
    who, action = (
        "the evaluator",
        "Compare the HR record with the rule book, then run the check again.",
    )
    blocker = Blocker(
        code=BlockerCode.SUP_RECHECK_MISMATCH,
        message="The readiness rules and the agent's own check disagree on: "
        + ", ".join(disagree)
        + ".",
        field="rules",
        next_action=f"{action} Who fixes it: {who}.",
    )
    text = f"{MISMATCH}\nWho fixes it: {who}. Next: {action}"
    narrative.record(
        ctx,
        "onb.",
        text,
        model=False,
        slots={},
        source_ref=source_ref(emp_id, "role"),
        produced_by=f"agents.onboarding@{__version__}",
    )
    return _result(ctx, Decision.ERROR, [blocker], [], text, steps, {})


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
    """SUP-05: recompute readiness from hr.db on every GO with the agent's own checker (not the
    engine the stage used); any disagreement with the ledger overrides the agent."""

    def recheck(result: AgentResult, ledger: LedgerPort) -> list[Blocker]:
        profile = load_profile(result.case_id)
        if profile is None:
            return [
                Blocker(
                    code=BlockerCode.ONB_TRAINING_MISSING,
                    message="recheck: HR has no record for the preparer",
                )
            ]
        mine = checker.check(profile, as_of)
        failed = _blockers(mine.blockers)
        facts = {f"onb.rule.{r}": o for r, o in mine.rules.items()} | {"onb.gate": mine.gate}
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
