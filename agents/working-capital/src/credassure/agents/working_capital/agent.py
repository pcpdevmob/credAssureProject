"""Working Capital Advisory agent, Gate 2 funding need (design-detail §2.4.3; WC-01..07, BR-01/05).

Code decides: the stored case files are validated (WC-01/02), the engines build the weekly cash
table, peak shortfall, recommendation rounded up to ₹1 lakh and the bridge from the indicative
request (WC-03..06), and every figure is a `wc.*` ledger fact with its inputs hash (lineage).
Any blocker -> NEEDS_INPUT with one question. The model only words the drivers from those facts
(wc_explain) with {slot} placeholders; code renders every figure and direction word, and a
draft with any figure outside a slot falls back to the template (WC-07).
"""

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any

from credassure.agents.working_capital import __version__
from credassure.core import narrative, slots
from credassure.core.blockers import BlockerCode, BlockerEffect, blocker_effect
from credassure.core.enums import AgentName, Decision
from credassure.core.errors import LLMError
from credassure.core.money import format_inr
from credassure.core.ports import LedgerPort, StageContext
from credassure.core.prompts import prompt_version
from credassure.core.prompts import registry as prompts
from credassure.core.results import AgentResult, Blocker, EvidenceRef
from credassure.engines import cashflow, validators
from credassure.engines.cashflow import CashTable, Recommendation
from credassure.engines.normaliser import find_all

PROMPT = "wc_explain"
ENGINE = "engines.cashflow"
ENGINE_VERSION = "1"  # bump when cashflow/validators change a result (lineage, scope #33)
FILES = {  # kind -> file name; inventory is information only (engines.cashflow)
    "order": "order.json",
    "opening_position": "opening_position.json",
    "costs": "costs.csv",
    "receipts": "receipts.csv",
    "receivables": "receivables.csv",
    "payables": "payables.csv",
}
# One question per stop (SUP-06): the first blocker in this order is asked about.
PRIORITY = (
    BlockerCode.WC_MISSING_FIELD,
    BlockerCode.WC_UNIT_OR_CURRENCY,
    BlockerCode.WC_DATE_OUT_OF_RANGE,
    BlockerCode.WC_CONFLICT_TOTALS,
    BlockerCode.WC_DUPLICATE_ID,
    BlockerCode.WC_UNSOURCED_OFFSET,
)


def version() -> str:
    return __version__


@dataclass(frozen=True)
class CaseInputs:
    """The stage's inputs, loaded read-only from the case's latest file per kind."""

    files: cashflow.CaseFiles | None
    sources: Mapping[str, str]  # kind -> sha256 of the stored file
    indicative: Decimal
    weeks: int = 26
    blockers: list[Blocker] = field(default_factory=list)
    warnings: list[Blocker] = field(default_factory=list)

    @property
    def source_ref(self) -> str:
        return "case_files:" + ",".join(f"{k}@{v[:12]}" for k, v in sorted(self.sources.items()))

    @property
    def input_hash(self) -> str:
        """Lineage (#33): files, indicative request, horizon and engine version."""
        parts = [f"{k}={v}" for k, v in sorted(self.sources.items())]
        parts += [
            f"indicative={self.indicative}",
            f"weeks={self.weeks}",
            f"{ENGINE}@{ENGINE_VERSION}",
        ]
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def load_inputs(
    stored: Mapping[str, tuple[str, Any]], indicative: Decimal, weeks: int = 26
) -> CaseInputs:
    """``stored``: kind -> (sha256, parsed payload). A missing file blocks before validation."""
    sources = {kind: sha for kind, (sha, _) in stored.items() if kind in FILES}
    missing = [
        Blocker(
            code=BlockerCode.WC_MISSING_FIELD,
            field=kind,
            message=f"The {FILES[kind]} file has not been uploaded.",
            next_action=f"Upload {FILES[kind]}.",
        )
        for kind in FILES
        if kind not in stored
    ]
    if missing:
        return CaseInputs(None, sources, indicative, weeks, missing)
    payload = {kind: stored[kind][1] for kind in FILES}
    files = cashflow.CaseFiles(
        order=payload["order"],
        opening=payload["opening_position"],
        costs=payload["costs"],
        receipts=payload["receipts"],
        receivables=payload["receivables"],
        payables=payload["payables"],
    )
    blockers, warnings = validators.validate(files, weeks)
    return CaseInputs(files, sources, indicative, weeks, blockers, warnings)


def facts_for(table: CashTable, rec: Recommendation) -> dict[str, tuple[Decimal | int | str, str]]:
    """Every wc.* fact: key -> (value, unit). Shared by the agent and the re-check (SUP-05)."""
    out: dict[str, tuple[Decimal | int | str, str]] = {
        "wc.peak_shortfall": (rec.peak_shortfall, "INR"),
        "wc.peak_week": (rec.peak_week, "week"),
        "wc.shortfall_weeks": (table.shortfall_weeks, "weeks"),
        "wc.min_buffer": (rec.min_cash_buffer, "INR"),
        "wc.undrawn_limits": (rec.undrawn_limits, "INR"),
        "wc.mitigations": (rec.mitigations, "INR"),
        "wc.recommended_amount": (rec.recommended_amount, "INR"),
    }
    out |= {f"wc.bridge.{line}": (amount, "INR") for line, amount in rec.bridge}
    rows = [
        {
            "week": r.week,
            "inflow": str(r.inflow),
            "outflow": str(r.outflow),
            "cumulative": str(r.cumulative),
        }
        for r in table.rows
    ]
    out["wc.cash_table"] = (json.dumps(rows, separators=(",", ":")), "json")
    return out


def _file(b: Blocker) -> str:
    return FILES.get(str(b.field or "").split(".")[0], "the case file")


def question(blockers: list[Blocker]) -> str:
    first = min(blockers, key=lambda b: PRIORITY.index(b.code) if b.code in PRIORITY else 99)
    if first.code is BlockerCode.WC_MISSING_FIELD and "." in str(first.field):
        name = str(first.field).split(".", 1)[1].replace("_", " ")
        return f"What is the {name} for this case? Please upload {_file(first)} with it filled in."
    if first.code is BlockerCode.WC_MISSING_FIELD:
        return f"Can you upload {_file(first)} for this case?"
    return f"{first.message} Can you upload a corrected {_file(first)}?"


def template(rec: Recommendation, table: CashTable) -> str:
    if rec.recommended_amount == 0:
        dip = (
            f"Cumulative cash falls to a peak shortfall of {format_inr(rec.peak_shortfall)} in "
            f"week {rec.peak_week}. "
            if rec.peak_shortfall > 0
            else "Cumulative cash never falls below zero. "
        )
        return (
            dip + f"Undrawn credit limits of {format_inr(rec.undrawn_limits)} and confirmed "
            f"mitigations of {format_inr(rec.mitigations)} cover it together with the minimum "
            f"cash buffer of {format_inr(rec.min_cash_buffer)}, so no new facility is needed; "
            f"the indicative request was {format_inr(rec.bridge[0][1])}."
        )
    return (
        f"Cumulative cash falls to its lowest point in week {rec.peak_week}, a peak shortfall of "
        f"{format_inr(rec.peak_shortfall)}, and stays below zero for {table.shortfall_weeks} "
        f"weeks. Adding the minimum cash buffer of {format_inr(rec.min_cash_buffer)} and "
        f"subtracting undrawn credit limits of {format_inr(rec.undrawn_limits)} and confirmed "
        f"mitigations of {format_inr(rec.mitigations)} gives a recommended facility of "
        f"{format_inr(rec.recommended_amount)} (rounded up), against the "
        f"indicative request of {format_inr(rec.bridge[0][1])}."
    )


def narrative_slots(rec: Recommendation, table: CashTable) -> dict[str, str]:
    """WC-07: every value and direction word the model may use, rendered by code. A zero offset
    has no slot, so the model cannot dwell on it."""
    request = rec.bridge[0][1]
    out = {
        "wc.peak_shortfall": slots.money(rec.peak_shortfall),
        "wc.peak_week": str(rec.peak_week),
        "wc.recommended_amount": slots.money(rec.recommended_amount),
        "wc.request": slots.money(request),
        "cmp.recommended_vs_request": slots.compare(rec.recommended_amount, request),
    }
    optional = {
        "wc.shortfall_weeks": (table.shortfall_weeks, str(table.shortfall_weeks)),
        "wc.min_buffer": (rec.min_cash_buffer, slots.money(rec.min_cash_buffer)),
        "wc.undrawn_limits": (rec.undrawn_limits, slots.money(rec.undrawn_limits)),
        "wc.mitigations": (rec.mitigations, slots.money(rec.mitigations)),
    }
    out |= {key: text for key, (value, text) in optional.items() if value}
    return out


def _explain(
    ctx: StageContext, rec: Recommendation, table: CashTable
) -> tuple[str | None, str | None]:
    """(slot-rendered model draft or None for the template, prompt used); the Critic checks it."""
    names = "\n".join(sorted(narrative_slots(rec, table)))
    reply, used = narrative.draft(ctx, PROMPT, prompts()[PROMPT].render(slots=names))
    if reply is None:
        return None, used
    rendered = slots.render(reply, narrative_slots(rec, table), required=["wc.recommended_amount"])
    return rendered, used


A1_PROMPT = "a1_wc_calc"


def _a1_amount(ctx: StageContext, inputs: CaseInputs, table: CashTable) -> Decimal | None:
    """Ablation A1 only: the model turns the weekly flows into the recommended facility."""
    if ctx.llm is None or inputs.files is None:
        return None
    opening = inputs.files.opening
    weeks = "\n".join(f"week {r.week}: in {r.inflow}, out {r.outflow}" for r in table.rows)
    prompt = prompts()[A1_PROMPT].render(
        opening=json.dumps(opening, default=str, sort_keys=True), weeks=weeks
    )
    try:
        reply = ctx.llm.complete(prompt, name=A1_PROMPT)
    except LLMError:
        return None
    amounts = [h.value for h in find_all(reply) if h.kind == "money"]  # never a week number
    return amounts[0] if amounts and isinstance(amounts[0], Decimal) else None


def run(ctx: StageContext) -> AgentResult:
    inputs: CaseInputs = ctx.tools.call("validate_case_files", ctx.case_id)
    steps = 1
    if inputs.blockers or inputs.files is None:
        ctx.ledger.put_fact(
            ctx.case_id,
            "wc.gate",
            "NEEDS_INPUT",
            unit="enum",
            source_type="case_file",
            source_ref=inputs.source_ref,
            produced_by=f"engines.validators@{ENGINE_VERSION}",
            input_hash=inputs.input_hash,
        )
        blockers = [*inputs.blockers, *inputs.warnings]
        text = "Funding need is waiting for case data:\n" + "\n".join(
            f"- {b.message}" for b in inputs.blockers
        )
        narrative.record(  # validator messages are code-rendered from the case files
            ctx,
            "wc.",
            text,
            model=False,
            slots={f"blocker.{i}": b.message for i, b in enumerate(inputs.blockers)},
            source_ref=inputs.source_ref,
            produced_by=f"engines.validators@{ENGINE_VERSION}",
            input_hash=inputs.input_hash,
        )
        return _result(
            ctx,
            Decision.NEEDS_INPUT,
            blockers,
            [EvidenceRef(kind="ledger_fact", ref_id="wc.gate")],
            text,
            steps,
            {},
            question=question(inputs.blockers),
        )
    table: CashTable = ctx.tools.call(
        "compute_cash_table", ctx.case_id, {"files": inputs.files, "weeks": inputs.weeks}
    )
    rec: Recommendation = ctx.tools.call(
        "compute_recommendation",
        ctx.case_id,
        {"files": inputs.files, "table": table, "indicative": inputs.indicative},
    )
    steps += 2
    versions: dict[str, str] = {}
    if ctx.ablation == "A1":  # the model calculates the recommendation (BRD §12); ablation only
        amount = _a1_amount(ctx, inputs, table)
        steps += 1
        if amount is None:
            q = "Ablation A1 needs the model to calculate the funding need, and it is unavailable."
            return _result(ctx, Decision.NEEDS_INPUT, [], [], q, steps, {}, question=q)
        rec = replace(rec, recommended_amount=amount)
        versions[A1_PROMPT] = prompt_version(A1_PROMPT)
    facts = facts_for(table, rec)
    drafted, used = _explain(ctx, rec, table)
    if used is not None:
        steps += 1
        versions[used] = prompt_version(used)
    # Facts after the model call: a ModelUnavailable retry (template path) writes them once.
    evidence = []
    for key, (value, unit) in [*facts.items(), ("wc.gate", ("GO", "enum"))]:
        ctx.ledger.put_fact(
            ctx.case_id,
            key,
            value,
            unit=unit,
            source_type="case_file",
            source_ref=inputs.source_ref,
            produced_by=(  # lineage says who made the number (A1: the model, not the engine)
                f"model:{A1_PROMPT}@{prompt_version(A1_PROMPT)}"
                if ctx.ablation == "A1" and key == "wc.recommended_amount"
                else f"{ENGINE}@{ENGINE_VERSION}"
            ),
            input_hash=inputs.input_hash,
        )
        evidence.append(EvidenceRef(kind="ledger_fact", ref_id=key))
    text = drafted or template(rec, table)
    narrative.record(
        ctx,
        "wc.",
        text,
        model=drafted is not None,
        slots=narrative_slots(rec, table),
        source_ref=inputs.source_ref,
        produced_by=f"{ENGINE}@{ENGINE_VERSION}",
        input_hash=inputs.input_hash,
    )
    return _result(
        ctx,
        Decision.GO,
        list(inputs.warnings),  # D5 warnings never gate
        evidence,
        text,
        steps,
        versions,
        output_ref="wc.cash_table",
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
    output_ref: str | None = None,
) -> AgentResult:
    return AgentResult(
        agent=AgentName.WORKING_CAPITAL,
        case_id=ctx.case_id,
        stage=ctx.stage,
        tenant_id=ctx.tenant_id,
        decision=decision,
        evidence=evidence,
        blockers=blockers,
        question=question,
        output_ref=output_ref,
        narrative=narrative,
        prompt_versions=versions,
        steps_used=steps,
        trace_id=ctx.trace_id,
        agent_version=__version__,
    )


def make_recheck(
    load: Callable[[str], CaseInputs],
) -> Callable[[AgentResult, LedgerPort], list[Blocker]]:
    """SUP-05: recompute every wc.* fact from the stored files on every GO; any difference
    overrides the agent (BR-11)."""

    def recheck(result: AgentResult, ledger: LedgerPort) -> list[Blocker]:
        inputs = load(result.case_id)
        gate = [b for b in inputs.blockers if blocker_effect(b.code) is not BlockerEffect.WARNING]
        if gate or inputs.files is None:
            return gate
        table = cashflow.cash_table(inputs.files, inputs.weeks)
        rec = cashflow.recommend(inputs.files, table, indicative=inputs.indicative)
        expected = {k: str(v) for k, (v, _) in facts_for(table, rec).items()} | {"wc.gate": "GO"}
        return [
            Blocker(
                code=BlockerCode.SUP_RECHECK_MISMATCH,
                message=f"recheck: ledger {key}={'<json>' if key == 'wc.cash_table' else got}, "
                f"recomputed {'<json>' if key == 'wc.cash_table' else want}",
            )
            for key, want in sorted(expected.items())
            if (got := ledger.get(result.case_id, key)) != want
        ]

    return recheck
