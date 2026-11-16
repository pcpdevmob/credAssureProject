"""LendWise agent, Gate 3 lender comparison (design-detail §2.4.4/§2.4.7; LW-01..11, LW-14).

Code decides: each uploaded offer is audited for material terms, instalment and schedule dates
(LW-02/03), its schedule of charges is parsed for charges the offer leaves out (LW-04, ADR 0021),
it is priced by IRR with GST on fees and the CGTMSE fee (LW-05..08, ADR 0012), its repayments are
run through the case's cash table (LW-09/10) and eligible offers are ranked (LW-11). GO needs at
least two comparable, affordable offers (LW-14). Every figure is an `lw.*` ledger fact.

The model does two things only. It reads each schedule of charges (one call per offer, in
parallel) and lists the charges with verbatim source spans; any charge whose span is not in the
document is discarded, and the result is used only when it agrees with the code's own parse of
the table, otherwise the code parse stands (`lw.kfs.<doc>.extraction` records which). It also
words the comparison with {slot} placeholders that code renders. Document text is spotlighted
data and never chooses a rank, a gate or a tool (BR-15). Nothing here accepts an offer (BR-13).
"""

import contextvars
import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from credassure.agents.lendwise import __version__
from credassure.core import narrative, slots
from credassure.core.blockers import BlockerCode, BlockerEffect, blocker_effect
from credassure.core.enums import AgentName, Decision
from credassure.core.errors import LLMError
from credassure.core.ports import LedgerPort, StageContext, ToolPort
from credassure.core.prompts import prompt_version
from credassure.core.prompts import registry as prompts
from credassure.core.results import AgentResult, Blocker, EvidenceRef
from credassure.core.structured import complete_model
from credassure.engines import affordability, cashflow, loancost, offer_audit, ranking
from credassure.engines.loancost import Charge
from credassure.engines.normaliser import find_all
from credassure.security.spotlight import spotlight

EXTRACT, EXPLAIN = "lw_kfs_extract", "lw_explain"
PAISE = Decimal("0.01")
MAX_OFFERS = 4  # BRD §4.1 compares three; four still fits the 10-step cap (SUP-07)
ENGINE = "engines.loancost"
ENGINE_VERSION = "1"  # bump when an LW engine changes a result (lineage, scope #33)
REASONS = {  # plain words for each flag; the narrative's reason slots add the computed detail
    BlockerCode.LW_MISSING_MATERIAL_TERM: "it is missing a material term, so it is not compared",
    BlockerCode.LW_INSTALMENT_MISMATCH: "its stated instalment does not match the recomputed one",
    BlockerCode.LW_SCHEDULE_DATE_MISMATCH: "its first repayment date does not match its schedule",
    BlockerCode.LW_NOT_AFFORDABLE: "its repayments would push cash below the minimum buffer",
    BlockerCode.LW_LATE_OR_SHORT: "it arrives after the cash low point or covers too little",
}


@dataclass(frozen=True)
class Position:
    """The funding position offers are checked against, from the case files (ADR 0021)."""

    cumulative: tuple[Decimal, ...]
    available: Decimal  # undrawn limits + every evidenced mitigation
    buffer: Decimal
    need: Decimal
    peak_week: int
    week1: date


@dataclass(frozen=True)
class ReferenceRate:
    id: str
    value_pct: Decimal
    source_doc_id: str


@dataclass(frozen=True)
class Inputs:
    """The stage's inputs, loaded read-only from the case's uploads (LW-01, SUP-08)."""

    offers: tuple[dict[str, Any], ...]  # latest version per offer_id
    schedules: Mapping[str, str]  # KFS doc_id -> body text
    enterprise_class: str
    position: Position | None  # None while the funding inputs are blocked
    sources: Mapping[str, str] = field(default_factory=dict)  # upload label -> sha256
    reference_rates: tuple[ReferenceRate, ...] = ()

    @property
    def source_ref(self) -> str:
        return "case_files:" + ",".join(f"{k}@{v[:12]}" for k, v in sorted(self.sources.items()))

    @property
    def input_hash(self) -> str:
        parts = [f"{k}={v}" for k, v in sorted(self.sources.items())]
        parts.append(f"{ENGINE}@{ENGINE_VERSION}")
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()

    def schedule_id(self, offer: Mapping[str, Any]) -> str:
        return f"{offer['kfs_doc_id']}-SCH"


def position(files: cashflow.CaseFiles, indicative: Decimal, weeks: int, week1: date) -> Position:
    table = cashflow.cash_table(files, weeks)
    rec = cashflow.recommend(files, table, indicative=indicative)
    undrawn, mitigations = cashflow.available_limits(files.opening)  # all evidenced (ADR 0021)
    return Position(
        tuple(table.cumulative()),
        undrawn + mitigations,
        rec.min_cash_buffer,
        rec.recommended_amount,
        table.peak_week,
        week1,
    )


def load_inputs(
    uploads: Sequence[tuple[str, str, Any]],
    enterprise_class: str,
    pos: Position | None,
    reference_rates: Sequence[ReferenceRate] = (),
) -> Inputs:
    """``uploads``: (kind, sha256, payload) oldest first. The newest upload of an offer version
    or KFS document wins; each offer is compared at its highest uploaded version."""
    offers: dict[str, tuple[int, str, dict[str, Any]]] = {}
    schedules: dict[str, tuple[str, str]] = {}
    for kind, sha, payload in uploads:
        if kind == "offer":
            oid, ver = str(payload["offer_id"]), int(payload["version"])
            if oid not in offers or ver >= offers[oid][0]:
                offers[oid] = (ver, sha, payload)
        elif kind == "kfs":
            schedules[str(payload["doc_id"])] = (sha, str(payload["text"]))
    sources = {f"offer:{oid}.v{v}": sha for oid, (v, sha, _) in offers.items()}
    sources |= {f"kfs:{d}": sha for d, (sha, _) in schedules.items()}
    return Inputs(
        tuple(o for _, (_, _, o) in sorted(offers.items())),
        {d: text for d, (_, text) in schedules.items()},
        enterprise_class,
        pos,
        sources,
        tuple(reference_rates),
    )


# ---- composition: the same code for the run, the re-check and the read-only preview ------------
@dataclass(frozen=True)
class OfferResult:
    offer: Mapping[str, Any]
    audit: offer_audit.Audit
    priced: loancost.Priced | None = None
    gst: Decimal | None = None
    fit: affordability.Fit | None = None

    @property
    def key(self) -> str:
        return f"lw.{self.offer['offer_id']}.v{self.offer['version']}"

    @property
    def flags(self) -> list[str]:
        codes = {f.split(":")[0] for f in self.audit.flags}
        if self.fit is not None and not self.fit.affordable:
            codes.add(BlockerCode.LW_NOT_AFFORDABLE.value)
        if self.fit is not None and (self.fit.late or self.fit.short):
            codes.add(BlockerCode.LW_LATE_OR_SHORT.value)
        return sorted(codes)

    @property
    def eligible(self) -> bool:
        f = self.fit
        return (
            self.audit.comparable and f is not None and f.affordable and not f.late and not f.short
        )


@dataclass(frozen=True)
class Comparison:
    offers: tuple[OfferResult, ...]
    ranking: ranking.Ranking | None  # None in the preview (funding not GO)


def complete(offer: Mapping[str, Any]) -> bool:
    return not [t for t in offer_audit.MATERIAL_TERMS if t not in offer]


def compare(
    tools: ToolPort,
    case_id: str,
    inputs: Inputs,
    hidden: Mapping[str, Sequence[Charge]],
    apr_override: Mapping[str, Decimal] | None = None,
) -> Comparison:
    """Audit, price, check affordability and rank, all through the engine tools (4 calls).

    A complete offer whose schedule is not uploaded is audited but never priced, so no APR is
    shown without its hidden charges. Undeclared rows code cannot read are flagged (LW-04)."""
    schedules = {
        o["offer_id"]: offer_audit.parse_schedule(inputs.schedules[inputs.schedule_id(o)])
        for o in inputs.offers
        if complete(o) and inputs.schedule_id(o) in inputs.schedules
    }
    unpriced = {
        oid: offer_audit.unpriced_rows(o, schedules[oid])
        for o in inputs.offers
        if (oid := o["offer_id"]) in schedules
    }
    audits: dict[str, offer_audit.Audit] = tools.call(
        "audit_offer",
        case_id,
        {
            "offers": inputs.offers,
            "hidden": hidden,
            "unpriced": unpriced,
            "enterprise_class": inputs.enterprise_class,
        },
    )
    priceable = [
        o
        for o in inputs.offers
        if not audits[o["offer_id"]].missing_terms and o["offer_id"] in schedules
    ]
    priced: dict[str, tuple[loancost.Priced, Decimal]] = tools.call(
        "price_offer", case_id, {"offers": priceable, "hidden": hidden}
    )
    for oid, apr in (apr_override or {}).items():  # ablation A1: the model's APR, not the engine's
        if oid in priced:
            priced[oid] = (replace(priced[oid][0], apr=apr), priced[oid][1])
    fits: dict[str, affordability.Fit] = {}
    order = None
    if inputs.position is not None:
        comparable = [o for o in priceable if audits[o["offer_id"]].comparable]
        fits = tools.call(
            "check_affordability",
            case_id,
            {
                "position": inputs.position,
                "offers": comparable,
                "flows": {o["offer_id"]: priced[o["offer_id"]][0].flows for o in comparable},
            },
        )
    results = tuple(
        OfferResult(
            o,
            audits[o["offer_id"]],
            priced[o["offer_id"]][0] if o["offer_id"] in priced else None,
            priced[o["offer_id"]][1] if o["offer_id"] in priced else None,
            fits.get(o["offer_id"]),
        )
        for o in inputs.offers
    )
    if inputs.position is not None:
        candidates = [
            ranking.Candidate(
                r.offer["offer_id"],
                r.eligible,
                r.priced.apr,
                r.priced.total_cost,
                date.fromisoformat(str(r.offer["disbursal_date"])),
            )
            for r in results
            if r.priced is not None
        ]
        order = tools.call(
            "rank_offers", case_id, {"candidates": candidates, "need": inputs.position.need}
        )
    return Comparison(results, order)


def facts_for(c: Comparison, inputs: Inputs) -> dict[str, tuple[Decimal | int | str, str]]:
    """Every lw.* fact the comparison yields: key -> (value, unit). Shared with the re-check."""
    out: dict[str, tuple[Decimal | int | str, str]] = {}
    rank_of = {oid: n for n, oid in enumerate(c.ranking.order, 1)} if c.ranking else {}
    for r in c.offers:
        k = r.key
        out[f"{k}.flags"] = (",".join(r.flags) or "none", "codes")
        out[f"{k}.comparable"] = (str(r.audit.comparable).lower(), "bool")
        if r.priced is not None and r.gst is not None:
            # paise, half-up; CGST + SGST as an intra-state supply (home state IN-MH, ADR 0021)
            gst = r.gst.quantize(PAISE, rounding=ROUND_HALF_UP)
            cgst = (gst / 2).quantize(PAISE, rounding=ROUND_HALF_UP)
            out |= {
                f"{k}.apr": (r.priced.apr, "rate"),
                f"{k}.amount_received": (r.priced.amount_received, "INR"),
                f"{k}.total_repayment": (r.priced.total_repayment, "INR"),
                f"{k}.total_cost": (r.priced.total_cost, "INR"),
                f"{k}.gst": (gst, "INR"),
                f"{k}.cgst": (cgst, "INR"),
                f"{k}.sgst": (gst - cgst, "INR"),
            }
        if r.fit is not None:
            out[f"{k}.affordable"] = (str(r.fit.affordable).lower(), "bool")  # LW-09
            out[f"{k}.eligible"] = (str(r.eligible).lower(), "bool")  # + on time, enough
            out[f"{k}.lowest_cash"] = (r.fit.lowest_cash, "INR")
            if r.fit.breach_week is not None:
                out[f"{k}.breach_week"] = (r.fit.breach_week, "week")  # 9d reason code
        if r.offer["offer_id"] in rank_of:
            out[f"{k}.rank"] = (rank_of[r.offer["offer_id"]], "rank")
    if c.ranking is not None:
        out["lw.ranking"] = (",".join(c.ranking.order) or "none", "offer_ids")
        out["lw.gate"] = (c.ranking.gate, "enum")
    if any(o.get("rate_type") == "floating" for o in inputs.offers):
        for rate in inputs.reference_rates:  # LW-08 context, cited (R-RATE-02)
            out[f"lw.reference_rate.{rate.id}"] = (rate.value_pct / 100, "rate")
    return out


# ---- KFS charge extraction (LW-04): the model lists, code verifies ------------------------------
class ExtractedCharge(BaseModel):
    name: str = Field(max_length=120)
    timing: Literal["upfront", "monthly", "annual"]
    value_text: str = Field(max_length=200)
    source_span: str = Field(max_length=400)


class KfsChargeExtraction(BaseModel):
    charges: list[ExtractedCharge] = Field(max_length=30)


def _flat(text: str) -> str:
    """Spotlighting joins words with ^; a span is verbatim when it matches modulo that."""
    return re.sub(r"[\s^]+", " ", text).strip()


def code_charges(schedule: str) -> set[Charge]:
    rows = offer_audit.parse_schedule(schedule)
    return {c for r in rows if (c := offer_audit.row_charge(r.name, r.timing, r.amount_text))}


def verified(extraction: KfsChargeExtraction, schedule: str) -> set[Charge]:
    """Charges whose span, name and value all appear verbatim in the document; others dropped."""
    doc, out = _flat(schedule), set()
    for c in extraction.charges:
        span, name, value = _flat(c.source_span), _flat(c.name), _flat(c.value_text)
        if not span or span not in doc or name not in span or value not in span:
            continue  # anti-hallucination: not in the document, not a charge
        charge = offer_audit.row_charge(name, c.timing, value)
        if charge is not None:
            out.add(charge)
    return out


def _extract(llm: Any, doc_id: str, schedule: str, guard: bool = True) -> set[Charge] | None:
    if guard:
        spot = spotlight([(doc_id, schedule)])
        prompt = prompts()[EXTRACT].render(preamble=spot.preamble, document=spot.text)
    else:  # ablation A5: the document goes in raw, not marked as data
        prompt = prompts()[EXTRACT].render(preamble="", document=schedule)
    try:
        return verified(complete_model(llm, EXTRACT, KfsChargeExtraction, prompt), schedule)
    except LLMError:  # slow or broken model: the code parse stands
        return None


def extract_all(
    ctx: StageContext, inputs: Inputs
) -> tuple[dict[str, list[Charge]], dict[str, str]]:
    """Hidden charges per offer and, per schedule, whether the model's reading was kept."""
    todo = [o for o in inputs.offers if complete(o)]
    model: dict[str, set[Charge] | None] = {}
    # A regeneration pass only redrafts the wording: the extraction is not repeated (NFR-03).
    if ctx.llm is not None and todo and not ctx.findings and not ctx.template_only:
        with ThreadPoolExecutor(max_workers=3) as pool:  # scope #22: shared limiter in the client
            futures = {
                o["offer_id"]: pool.submit(
                    contextvars.copy_context().run,  # the stage budget is a ContextVar
                    _extract,
                    ctx.llm,
                    inputs.schedule_id(o),
                    inputs.schedules[inputs.schedule_id(o)],
                    ctx.ablation != "A5",
                )
                for o in todo
            }
            model = {oid: f.result() for oid, f in futures.items()}
    hidden, source = {}, {}
    for o in todo:
        doc = inputs.schedule_id(o)
        rows = offer_audit.parse_schedule(inputs.schedules[doc])
        hidden[o["offer_id"]] = offer_audit.hidden_charges(o, rows)
        got = model.get(o["offer_id"])
        source[doc] = (
            "model" if got is not None and got == code_charges(inputs.schedules[doc]) else "code"
        )
    return hidden, source


def code_hidden(inputs: Inputs) -> dict[str, list[Charge]]:
    return {
        o["offer_id"]: offer_audit.hidden_charges(
            o, offer_audit.parse_schedule(inputs.schedules[inputs.schedule_id(o)])
        )
        for o in inputs.offers
        if complete(o)
    }


# ---- narrative ---------------------------------------------------------------------------------
def _principal(r: OfferResult) -> Decimal:
    return Decimal(str(r.offer["principal"]))


def _why(r: OfferResult, position: Position | None) -> str | None:
    """9d reason codes: why an offer is not ranked, with the figures code computed (week, amount).
    The model may only repeat these clauses; any reason of its own is a Critic finding."""
    fit = r.fit
    for code in r.flags:  # sorted: the same priority the template has always used
        if code == BlockerCode.LW_NOT_AFFORDABLE.value:
            week = f" in week {fit.breach_week}" if fit and fit.breach_week else ""
            return f"its repayments would push cash below the minimum buffer{week}"
        if code == BlockerCode.LW_LATE_OR_SHORT.value and fit is not None and position is not None:
            parts = []
            if fit.late:
                low = position.peak_week
                parts.append(f"it is disbursed after the cash low point in week {low}")
            if fit.short:
                parts.append(
                    f"it lends {slots.money(_principal(r))} against the "
                    f"{slots.money(position.need)} needed"
                )
            return " and ".join(parts)
        if code in REASONS:
            return REASONS[BlockerCode(code)]
    return None


def narrative_slots(c: Comparison, position: Position | None = None) -> dict[str, str]:
    """LW: every value and reason the model may use, rendered by code (slots only)."""
    by_id = {r.offer["offer_id"]: r for r in c.offers}
    out: dict[str, str] = {}
    order = c.ranking.order if c.ranking else ()
    for n, oid in enumerate(order[:2], 1):
        p = by_id[oid].priced  # ranked offers are always priced
        if p is not None:
            out[f"rank{n}.offer"] = oid
            out[f"rank{n}.apr"] = slots.rate(p.apr)
            out[f"rank{n}.total_cost"] = slots.money(p.total_cost)
    if len(order) >= 2:
        first, second = by_id[order[0]], by_id[order[1]]
        a, b = first.priced, second.priced
        if a is not None and b is not None:
            out["cmp.rank1_vs_rank2"] = slots.compare(a.apr, b.apr)
            more_cost = b.total_cost - a.total_cost
            if more_cost > 0:
                out["reason.rank2.total_cost"] = (
                    f"{order[1]} costs {slots.money(more_cost)} more in total than {order[0]}"
                )
            upfront = (_principal(second) - b.amount_received) - (
                _principal(first) - a.amount_received
            )
            if upfront > 0:
                out["reason.rank2.upfront"] = (
                    f"{order[1]} deducts {slots.money(upfront)} more upfront than {order[0]}"
                )
    priced = [r for r in c.offers if r.priced is not None]
    if order and priced:
        headline = min(priced, key=lambda r: (Decimal(str(r.offer["annual_rate"])), r.key))
        top = by_id[order[0]].priced
        # Only when it is true: a cheaper-looking offer whose APR is higher than the first rank's.
        # An unranked headline offer with a lower APR is explained by its excluded.* reason.
        if headline.priced is not None and top is not None and headline.priced.apr > top.apr:
            out["headline.offer"] = headline.offer["offer_id"]
            out["headline.note"] = "has the lowest headline rate but a higher APR"
    for r in c.offers:
        if r.offer["offer_id"] in order:
            continue
        reason = _why(r, position)
        if reason:
            oid = r.offer["offer_id"]
            out[f"excluded.{oid}"] = f"{oid} is not ranked because {reason}"
    return out


def template(c: Comparison, position: Position | None = None) -> str:
    s = narrative_slots(c, position)
    if c.ranking is None or c.ranking.gate == "NOT_REQUIRED":
        return "No new facility is needed for this case, so the offers are audited but not ranked."
    parts = []
    if "rank1.offer" in s:
        parts.append(
            f"{s['rank1.offer']} ranks first with an APR of {s['rank1.apr']} and a total cost of "
            f"{s['rank1.total_cost']}."
        )
    if "rank2.offer" in s:
        parts.append(
            f"{s['rank2.offer']} follows at {s['rank2.apr']} (total cost {s['rank2.total_cost']})."
        )
    parts += [s[k] + "." for k in ("reason.rank2.total_cost", "reason.rank2.upfront") if k in s]
    if "headline.offer" in s:
        parts.append(
            f"{s['headline.offer']} {s['headline.note']} once fees, GST and charges count."
        )
    parts += [s[k] + "." for k in sorted(s) if k.startswith("excluded.")]
    if c.ranking.gate == "NO_GO":
        parts.append("Fewer than two offers are both comparable and affordable.")
    return " ".join(parts)


MEANINGS = {
    "rank1.offer": "the first-ranked offer",
    "rank1.apr": "the first offer's true annual cost (APR, fees and GST included)",
    "rank1.total_cost": "the first offer's total cost",
    "rank2.offer": "the second-ranked offer",
    "rank2.apr": "the second offer's true annual cost",
    "rank2.total_cost": "the second offer's total cost",
    "cmp.rank1_vs_rank2": "the words comparing the first APR with the second, such as lower than",
    "headline.offer": "an offer with the lowest advertised rate",
    "headline.note": "a clause saying that offer costs more once fees count",
}


def _meaning(key: str) -> str:
    if key.startswith(("excluded.", "reason.")):
        return "a complete clause giving a reason; write it as its own sentence"
    return MEANINGS[key]


def _example(values: Mapping[str, str]) -> str:
    """An example built from this case's placeholders only, so copying it is always valid."""
    parts = []
    if "rank1.offer" in values:
        parts.append("{rank1.offer} ranks first, with a true annual cost of {rank1.apr}.")
    if "cmp.rank1_vs_rank2" in values:
        parts.append("That is {cmp.rank1_vs_rank2} the {rank2.apr} of {rank2.offer}.")
    parts += [f"{{{k}}}." for k in sorted(values) if k.startswith("reason.")]
    if "headline.offer" in values:
        parts.append("{headline.offer} {headline.note}.")
    parts += [f"{{{k}}}." for k in sorted(values) if k.startswith("excluded.")]
    return " ".join(parts)


def _explain(
    ctx: StageContext, c: Comparison, position: Position | None
) -> tuple[str | None, str | None]:
    """(slot-rendered model draft or None for the template, prompt used); the Critic checks it."""
    if c.ranking is None or c.ranking.gate == "NOT_REQUIRED":
        return None, None
    values = narrative_slots(c, position)
    prompt = prompts()[EXPLAIN].render(
        slots="\n".join(f"{{{k}}} = {_meaning(k)}" for k in sorted(values)),
        example=_example(values),
        gate=c.ranking.gate,
    )
    reply, used = narrative.draft(ctx, EXPLAIN, prompt)
    if reply is None:
        return None, used
    required = ["rank1.offer"] if "rank1.offer" in values else []
    required += [k for k in values if k.startswith("excluded.")]
    return slots.render(reply, values, required=required), used


# ---- the stage ---------------------------------------------------------------------------------
def version() -> str:
    return __version__


def _missing(inputs: Inputs) -> str | None:
    if not inputs.offers:
        return "Can you upload the lender offers for this case (one JSON file per offer)?"
    if len(inputs.offers) > MAX_OFFERS:
        return f"This case has {len(inputs.offers)} offers; which {MAX_OFFERS} should be compared?"
    absent = sorted(
        {inputs.schedule_id(o) for o in inputs.offers if complete(o)} - set(inputs.schedules)
    )
    if absent:
        return f"Can you upload the schedule of charges {absent[0]} for this case?"
    return None


def ready(inputs: Inputs) -> bool:
    return _missing(inputs) is None


def run(ctx: StageContext) -> AgentResult:
    inputs: Inputs = ctx.tools.call("load_offers", ctx.case_id)
    steps = 1
    ask = _missing(inputs)
    if ask is not None or inputs.position is None:
        q = ask or "Can you resolve the funding-need question first?"
        return _asking(ctx, inputs, q, steps)
    need = ctx.ledger.get(ctx.case_id, "wc.recommended_amount")  # read-only wc.* (scope #24)
    if need is None or Decimal(need) != inputs.position.need:
        q = "The funding need has changed since it was calculated; can you re-run working capital?"
        return _asking(ctx, inputs, q, steps)
    hidden, source = extract_all(ctx, inputs)
    versions: dict[str, str] = {}
    if ctx.llm is not None and source:
        steps += len(source)
        versions[EXTRACT] = prompt_version(EXTRACT)
    override = None
    if ctx.ablation == "A1":  # the model calculates the APRs (BRD §12); one call for all offers
        override = _a1_aprs(ctx, inputs)
        steps += 1
        if override is None:
            q = "Ablation A1 needs the model to calculate APRs, and it is unavailable."
            return _asking(ctx, inputs, q, steps)
        versions[A1_PROMPT] = prompt_version(A1_PROMPT)
    c = compare(ctx.tools, ctx.case_id, inputs, hidden, override)
    steps += 4
    drafted, used = _explain(ctx, c, inputs.position)
    if used is not None:
        steps += 1
        versions[used] = prompt_version(used)
    facts = facts_for(c, inputs)
    facts |= {f"lw.kfs.{doc}.extraction": (how, "enum") for doc, how in source.items()}
    evidence = []
    for key, (value, unit) in facts.items():
        rate = key.startswith("lw.reference_rate.")
        ctx.ledger.put_fact(
            ctx.case_id,
            key,
            value,
            unit=unit,
            source_type="reference" if rate else "case_file",
            source_ref=_cite(inputs, key) if rate else inputs.source_ref,
            produced_by=(  # lineage says who made the number (A1: the model, not the engine)
                f"model:{A1_PROMPT}@{prompt_version(A1_PROMPT)}"
                if override is not None and key.endswith(".apr")
                else f"{ENGINE}@{ENGINE_VERSION}"
            ),
            input_hash=inputs.input_hash,
        )
        evidence.append(EvidenceRef(kind="ledger_fact", ref_id=key))
    decision, blockers = gate(c)
    text = drafted or template(c, inputs.position)
    narrative.record(
        ctx,
        "lw.",
        text,
        model=drafted is not None,
        slots=narrative_slots(c, inputs.position),
        source_ref=inputs.source_ref,
        produced_by=f"{ENGINE}@{ENGINE_VERSION}",
        input_hash=inputs.input_hash,
    )
    return _result(
        ctx,
        decision,
        blockers,
        evidence,
        text,
        steps,
        versions,
        output_ref="lw.ranking",
    )


A1_PROMPT = "a1_lw_apr"


def _a1_aprs(ctx: StageContext, inputs: Inputs) -> dict[str, Decimal] | None:
    """Ablation A1 only: the model computes each offer's APR from its terms (no engine)."""
    if ctx.llm is None:
        return None
    terms = json.dumps([_terms(o) for o in inputs.offers if complete(o)], default=str)
    try:
        reply = ctx.llm.complete(prompts()[A1_PROMPT].render(offers=terms), name=A1_PROMPT)
    except LLMError:
        return None
    out: dict[str, Decimal] = {}
    for line in reply.splitlines():
        oid, _, rest = line.partition(":")
        rates = [h.value for h in find_all(rest) if h.kind == "rate"]
        if oid.strip() and rates and isinstance(rates[0], Decimal):
            out[oid.strip()] = rates[0]
    want = {o["offer_id"] for o in inputs.offers if complete(o)}
    return out if want <= set(out) else None  # a missing or mislabelled offer is a model failure


def _terms(o: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("offer_id", "principal", "annual_rate", "tenure_months", "moratorium_months", "fees")
    return {k: o.get(k) for k in keys}


def _asking(ctx: StageContext, inputs: Inputs, q: str, steps: int) -> AgentResult:
    narrative.record(
        ctx,
        "lw.",
        q,
        model=False,
        slots={},
        source_ref=inputs.source_ref,
        produced_by=f"agents.lendwise@{__version__}",
    )
    return _result(ctx, Decision.NEEDS_INPUT, [], [], q, steps, {}, question=q)


def _cite(inputs: Inputs, key: str) -> str:
    rid = key.removeprefix("lw.reference_rate.")
    return next(r.source_doc_id for r in inputs.reference_rates if r.id == rid)


def gate(c: Comparison) -> tuple[Decision, list[Blocker]]:
    """LW-14: GO with at least two comparable, affordable offers (or no need at all)."""
    if c.ranking is None:
        raise ValueError("no gate without a funding position")
    per_offer = [
        Blocker(
            code=BlockerCode(flag),
            field=r.offer["offer_id"],
            message=f"{r.offer['offer_id']}: {REASONS.get(BlockerCode(flag), flag)}",
        )
        for r in c.offers
        for flag in r.flags
    ]
    if c.ranking.gate in ("GO", "NOT_REQUIRED"):  # warnings only; offers stay flagged in facts
        return Decision.GO, [
            b for b in per_offer if blocker_effect(b.code) is BlockerEffect.WARNING
        ]
    fewer = Blocker(
        code=BlockerCode.LW_FEWER_THAN_TWO_ELIGIBLE,
        message=f"{len(c.ranking.order)} of {len(c.offers)} offers are comparable and affordable; "
        "at least two are needed.",
        next_action="Ask the lenders for corrected offer documents and upload them.",
    )
    return Decision.NO_GO, [fewer, *per_offer]


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
        agent=AgentName.LENDWISE,
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
    tools: Callable[[], ToolPort], load: Callable[[str], Inputs]
) -> Callable[[AgentResult, LedgerPort], list[Blocker]]:
    """SUP-05: recompute every lw.* fact from the uploads with the code parse of each schedule
    on every GO; any difference overrides the agent (BR-11)."""

    def recheck(result: AgentResult, ledger: LedgerPort) -> list[Blocker]:
        inputs = load(result.case_id)
        if _missing(inputs) is not None or inputs.position is None:
            return [Blocker(code=BlockerCode.SUP_RECHECK_MISMATCH, message="recheck: inputs gone")]
        c = compare(tools(), result.case_id, inputs, code_hidden(inputs))
        decision, blockers = gate(c)
        expected = {k: str(v) for k, (v, _) in facts_for(c, inputs).items()}
        failed = [
            Blocker(
                code=BlockerCode.SUP_RECHECK_MISMATCH,
                message=f"recheck: ledger {key}={got}, recomputed {want}",
            )
            for key, want in sorted(expected.items())
            if (got := ledger.get(result.case_id, key)) != want
        ]
        if decision is not Decision.GO:
            failed += [b for b in blockers if blocker_effect(b.code) is BlockerEffect.GATE]
        return failed

    return recheck
