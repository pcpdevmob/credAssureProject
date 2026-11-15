"""Working Capital Advisory agent, Gate 2 funding need (design-detail §2.4.3; WC-01..07, BR-01/05).

Code decides: the stored case files are validated (WC-01/02), the engines build the weekly cash
table, peak shortfall, recommendation rounded up to ₹1 lakh and the bridge from the indicative
request (WC-03..06), and every figure is a `wc.*` ledger fact with its inputs hash (lineage).
Any blocker -> NEEDS_INPUT with one question. The model only words the drivers from those facts
(wc_explain); a reply with any number that is not a fact falls back to the template (WC-07).
"""

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from credassure.agents.working_capital import __version__
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
# VER-03 interim guard until the Critic (9d), as in onboarding.
BANNED = re.compile(
    r"(?-i:\bGO\b|\bNO_GO\b)|approv|accept|\bsign|guarantee|lender|\bbank|sanction|disburs"
    r"|interest|\brate\b|urgent|immediately",
    re.IGNORECASE,
)
# Amounts must be digits the normaliser can match to a fact; words and links never can.
_WORDS = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty"
    r"|fifty|hundred|thousand|lakh|lac|crore|cr|percent|half|quarter)s?\b|https?://|www\.",
    re.IGNORECASE,
)
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


def grounded(text: str, facts: Mapping[str, tuple[Decimal | int | str, str]], weeks: int) -> bool:
    """WC-07 until the Critic (9d): every amount is a ledger fact (₹1), every bare number a week
    fact or the horizon; rates, dates and unparsed digits are not allowed."""
    amounts = [abs(Decimal(v)) for v, unit in facts.values() if unit == "INR"]
    counts = {Decimal(v) for v, unit in facts.values() if unit in ("week", "weeks")} | {
        Decimal(weeks)
    }
    if _WORDS.search(text):
        return False
    hits = find_all(text)
    rest = list(text)
    for found in hits:
        rest[found.start : found.end] = " " * (found.end - found.start)
    if re.search(r"\d", "".join(rest)):  # identifiers like "Q1 FY27" are skipped by find_all
        return False
    for found in hits:
        value = found.value
        if found.kind == "money" and isinstance(value, Decimal):
            if not any(abs(abs(value) - a) <= 1 for a in amounts):
                return False
        elif found.kind == "number" and isinstance(value, Decimal):
            if value not in counts:
                return False
        else:
            return False
    return True


def _explain(
    ctx: StageContext, facts: Mapping[str, tuple[Decimal | int | str, str]], weeks: int
) -> str | None:
    if ctx.llm is None:
        return None
    lines = [
        f"{key}: {format_inr(Decimal(value)) if unit == 'INR' else value}"
        for key, (value, unit) in facts.items()
        if key != "wc.cash_table"
    ]
    prompt = prompts()[PROMPT].render(facts="\n".join(lines))
    try:
        reply = ctx.llm.complete(prompt, name=PROMPT).strip()
    except LLMError:  # slow or down model: the gate and figures are already decided
        return None
    if not reply or BANNED.search(reply) or not grounded(reply, facts, weeks):
        return None
    return reply


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
        return _result(
            ctx,
            Decision.NEEDS_INPUT,
            blockers,
            [EvidenceRef(kind="ledger_fact", ref_id="wc.gate")],
            "Funding need is waiting for case data:\n"
            + "\n".join(f"- {b.message}" for b in inputs.blockers),
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
    facts = facts_for(table, rec)
    drafted = _explain(ctx, facts, inputs.weeks)
    versions = {}
    if ctx.llm is not None:
        steps += 1
        versions[PROMPT] = prompt_version(PROMPT)
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
            produced_by=f"{ENGINE}@{ENGINE_VERSION}",
            input_hash=inputs.input_hash,
        )
        evidence.append(EvidenceRef(kind="ledger_fact", ref_id=key))
    return _result(
        ctx,
        Decision.GO,
        list(inputs.warnings),  # D5 warnings never gate
        evidence,
        drafted or template(rec, table),
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
