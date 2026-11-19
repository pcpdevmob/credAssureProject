"""LendWise negotiation: up to three rounds, one per invocation (design-detail §2.4.7 step 6;
LW-12/13/15, BR-09/10/13/15, ADR 0037).

A separate invocation after the comparison. Each call runs the next move in a fixed order
(``engines.negotiation.MOVES``: fee waiver, rate match, tenor change); a move with no target is
skipped without using a round, and each move runs at most once per case. Code picks the target and
the verified figure it cites, writes them as ledger facts, and fills the move's fixed template from
those facts only; no model writes any part of the message. The message goes to ``verify_claims``
(every figure must equal a ledger fact; no acceptance, approval or urgency wording) before the
simulated lender sees it. The lender's reply is scanned for injected instructions and stored masked
as display-only text (``reply_text``, linked to its ``round``; no agent may read it back, registry
``display_only``). A revised version is re-audited, re-priced and fit-checked together with the
other offers in one comparison; only then are the concession and the revised figures written, and
when the concession counts the revision is stored and the offers are re-ranked (``lw.ranking``,
``lw.gate``, per-offer facts), so the approver always sees the order with every counted
concession in it. The report becomes stale and must be regenerated before approval (ADR 0003 §3).

The fee waiver writes the same keys and the same message as before ADR 0037, under
``lw.negotiation.``; the rate match and the tenor change write under ``lw.negotiation.rate_match.``
and ``lw.negotiation.tenor_change.``, each with the ``round`` it ran in.
Nothing here accepts, signs or submits an offer (BR-13).
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import date
from decimal import Decimal
from string import Template
from typing import Any

from credassure.agents.lendwise.agent import (
    ENGINE,
    ENGINE_VERSION,
    NEGOTIATION,
    Comparison,
    Inputs,
    _result,
    code_hidden,
    compare,
    facts_for,
)
from credassure.core.enums import Decision
from credassure.core.findings import CriticFinding
from credassure.core.money import format_inr
from credassure.core.ports import StageContext
from credassure.core.results import AgentResult, Blocker, EvidenceRef
from credassure.engines import negotiation
from credassure.security.injection import scan
from credassure.security.pii import redact

TEMPLATE_ID = negotiation.FEE_WAIVER
ROUND = 1  # the fee waiver is always round 1 when it runs (LW-12)
CLOSING = (
    "This is a request for a revised offer only; the business will choose its lender separately.\n"
)
FEE_WAIVER_V1 = Template(
    "Dear $lender_name,\n\n"
    "Thank you for offer $offer_id. Its processing fee is $current_fee. "
    "Another lender's comparable offer for this proposal carries a processing fee of "
    "$competing_fee.\n\n"
    "We request that you waive or reduce the processing fee on offer $offer_id. " + CLOSING
)
RATE_MATCH_V1 = Template(
    "Dear $lender_name,\n\n"
    "Thank you for offer $offer_id. Its annual interest rate is $current_rate. "
    "Another lender's comparable offer for this proposal carries an annual interest rate of "
    "$competing_rate.\n\n"
    "We request that you match or reduce the annual interest rate on offer $offer_id. " + CLOSING
)
TENOR_CHANGE_V1 = Template(
    "Dear $lender_name,\n\n"
    "Thank you for offer $offer_id. Its first repayment falls due on $current_first. "
    "The business's cash position is lowest in the week starting $cash_low.\n\n"
    "We request a longer moratorium on offer $offer_id, so that the first repayment falls due on "
    "$requested_first, with the tenure extended by the same period and the instalment unchanged. "
    + CLOSING
)
NS = NEGOTIATION


PREFIX = {
    negotiation.FEE_WAIVER: NS,  # the pre-ADR-0037 keys, unchanged
    negotiation.RATE_MATCH: NS + "rate_match.",
    negotiation.TENOR_CHANGE: NS + "tenor_change.",
}


def prefix(move: str) -> str:
    """Where a move's facts live. Each move runs at most once, so its keys never collide; the
    round it ran in is its ``round`` fact."""
    return PREFIX[move]


def _fee(value: str, unit: str) -> str:
    """A fee from the ledger in words, exactly as stored: a share of the loan amount ("rate",
    shown as a percentage) or a fixed amount in rupees ("INR")."""
    if unit == "INR":
        return format_inr(Decimal(value))
    pct = (Decimal(value) * 100).normalize()
    return f"{format(pct, 'f')}% of the loan amount"


def _pct(value: str) -> str:
    pct = (Decimal(value) * 100).normalize()
    return f"{format(pct, 'f')}%"


def _unit(basis: str) -> str:
    return "rate" if basis == "pct_of_principal" else "INR"


Facts = dict[str, tuple[Any, str]]


def negotiate(ctx: StageContext) -> AgentResult:
    """The next round. Decision GO = a round ran, or no move is left (``complete``);
    NO_GO = the round's message failed verification and was not sent."""
    steps = 1
    inputs: Inputs = ctx.tools.call("load_offers", ctx.case_id)
    if ctx.ledger.get(ctx.case_id, "lw.gate") is None:
        q = "Can you run the lender comparison first?"
        return _result(ctx, Decision.NEEDS_INPUT, [], [], q, steps, {}, question=q)
    done = _csv(ctx.ledger.get(ctx.case_id, NS + "moves"))  # move:outcome, in order
    used = {m.partition(":")[0] for m in done}
    sent = sum(m.endswith(":sent") for m in done)
    if sent >= negotiation.MAX_ROUNDS or ctx.ledger.get(ctx.case_id, NS + "complete") == "true":
        return _done(ctx, Decision.GO, [], steps, "Negotiation is complete.", NS + "complete")
    for move in negotiation.MOVES:
        if move in used:
            continue
        plan = _plan(ctx, inputs, move)
        if plan is None:
            done.append(f"{move}:skipped")
            facts: Facts = {NS + "moves": (",".join(done), "codes")}
            if move == negotiation.FEE_WAIVER:  # BR-10: no verified competing fee, no message
                facts = {NS + "target": ("none", "offer_id"), NS + "status": ("none", "enum")}
                facts[NS + "moves"] = (",".join(done), "codes")
            _write(ctx, inputs, facts)
            continue
        return _round(ctx, inputs, move, plan, sent + 1, done, steps)
    _write(ctx, inputs, {NS + "complete": ("true", "bool")})
    text = "No verified competing fee; no message sent." if not sent else "No further move."
    return _done(ctx, Decision.GO, [], steps, text, NS + "target")


def _csv(value: str | None) -> list[str]:
    return [] if value in (None, "", "none") else str(value).split(",")


def _standings(ctx: StageContext, inputs: Inputs) -> list[negotiation.Standing]:
    """Every offer at its latest version, as the last comparison stored it."""

    def get(o: Mapping[str, Any], name: str) -> str | None:
        return ctx.ledger.get(ctx.case_id, f"lw.{o['offer_id']}.v{o['version']}.{name}")

    out = []
    for o in inputs.offers:
        rank, apr = get(o, "rank"), get(o, "apr")
        out.append(
            negotiation.Standing(
                o,
                get(o, "comparable") == "true",
                get(o, "eligible") == "true",
                None if rank is None else int(rank),
                None if apr is None else Decimal(apr),
                frozenset(_csv(get(o, "flags"))),
            )
        )
    return out


Plan = negotiation.Plan | negotiation.RateMatch | negotiation.TenorChange


def _plan(ctx: StageContext, inputs: Inputs, move: str) -> Plan | None:
    if move == negotiation.FEE_WAIVER:
        comparable = [s.offer for s in _standings(ctx, inputs) if s.comparable]
        return negotiation.plan(comparable)
    if move == negotiation.RATE_MATCH:
        return negotiation.rate_match(_standings(ctx, inputs))
    if inputs.position is None:
        return None
    pos = inputs.position
    return negotiation.tenor_change(_standings(ctx, inputs), pos.week1, pos.peak_week)


def _message(
    ctx: StageContext, move: str, plan: Plan, p: str, lender: str
) -> tuple[Facts, Callable[[], str], list[str]]:
    """The move's facts, a renderer that fills the template from the ledger only, and the keys
    the message may quote (LW-12: every slot comes back from the ledger)."""

    def get(key: str) -> str:
        return ctx.ledger.get(ctx.case_id, p + key) or ""

    if isinstance(plan, negotiation.Plan):
        facts: Facts = {
            p + "target": (plan.target_offer, "offer_id"),
            p + "template": (move, "id"),
            p + "current_fee": (plan.current_fee, _unit(plan.current_basis)),
            p + "competing_fee": (plan.competing_fee, _unit(plan.competing_basis)),
            p + "competing_offer": (plan.competing_offer, "offer_id"),
        }

        def fee() -> str:
            return FEE_WAIVER_V1.substitute(
                lender_name=lender,
                offer_id=get("target"),
                current_fee=_fee(get("current_fee"), _unit(plan.current_basis)),
                competing_fee=_fee(get("competing_fee"), _unit(plan.competing_basis)),
            )

        return facts, fee, [p + "current_fee", p + "competing_fee"]
    if isinstance(plan, negotiation.RateMatch):
        facts = {
            p + "target": (plan.target_offer, "offer_id"),
            p + "template": (move, "id"),
            p + "current_rate": (plan.current_rate, "rate"),
            p + "competing_rate": (plan.competing_rate, "rate"),
            p + "competing_offer": (plan.competing_offer, "offer_id"),
        }

        def rate() -> str:
            return RATE_MATCH_V1.substitute(
                lender_name=lender,
                offer_id=get("target"),
                current_rate=_pct(get("current_rate")),
                competing_rate=_pct(get("competing_rate")),
            )

        return facts, rate, [p + "current_rate", p + "competing_rate"]
    facts = {
        p + "target": (plan.target_offer, "offer_id"),
        p + "template": (move, "id"),
        p + "current_first_repayment": (plan.current_first.isoformat(), "date"),
        p + "requested_first_repayment": (plan.requested_first.isoformat(), "date"),
        p + "cash_low_week_start": (plan.cash_low_week_start.isoformat(), "date"),
        p + "extra_months": (plan.extra_months, "months"),
    }

    def tenor() -> str:
        return TENOR_CHANGE_V1.substitute(
            lender_name=lender,
            offer_id=get("target"),
            current_first=get("current_first_repayment"),
            cash_low=get("cash_low_week_start"),
            requested_first=get("requested_first_repayment"),
        )

    keys = ["current_first_repayment", "requested_first_repayment", "cash_low_week_start"]
    return facts, tenor, [p + k for k in keys]


def _terms(plan: Plan) -> dict[str, Any] | None:
    if isinstance(plan, negotiation.RateMatch):
        return {"cited_rate": str(plan.competing_rate)}
    if isinstance(plan, negotiation.TenorChange):
        return {"extra_months": plan.extra_months}
    return None


_COUNTS = {
    negotiation.FEE_WAIVER: negotiation.concession_counts,
    negotiation.RATE_MATCH: negotiation.rate_counts,
    negotiation.TENOR_CHANGE: negotiation.tenor_counts,
}


def _round(
    ctx: StageContext,
    inputs: Inputs,
    move: str,
    plan: Plan,
    round_no: int,
    done: list[str],
    steps: int,
) -> AgentResult:
    p = prefix(move)
    target = next(o for o in inputs.offers if o["offer_id"] == plan.target_offer)
    facts, render, keys = _message(ctx, move, plan, p, str(target["lender_name"]))
    _write(ctx, inputs, facts)
    message = render()
    findings: list[CriticFinding] = ctx.tools.call(
        "verify_claims", ctx.case_id, {"text": message, "keys": keys, "stage": "lendwise"}
    )
    steps += 1
    if findings:  # the Verification Critic (VER-01/03): blocked, never sent
        blockers = [Blocker(code=f.code, message=f.message) for f in findings[:5]]
        done.append(f"{move}:blocked")
        _write(
            ctx,
            inputs,
            {p + "status": ("blocked", "enum"), NS + "moves": (",".join(done), "codes")},
        )
        return _done(
            ctx, Decision.NO_GO, blockers, steps, "The message failed verification.", p + "target"
        )
    request: dict[str, Any] = {
        "lender_id": target["lender_id"],
        "template_id": move,
        "message": message,
        "offer": target,
        "schedule": inputs.schedules[inputs.schedule_id(target)],
    }
    if (terms := _terms(plan)) is not None:
        request["terms"] = terms
    reply = ctx.tools.call("lender_send_template", ctx.case_id, request)
    steps += 1
    # BR-15: the reply is data; a planted instruction is only recorded (A5: scanner off)
    flags = [] if ctx.ablation == "A5" else scan(reply.text)
    after: Facts = {
        p + "message": (message, "text"),
        p + "status": ("sent", "enum"),
        p + "reply_flags": (",".join(flags) or "none", "codes"),
        p + "round": (round_no, "count"),
        p + "reply_text": (redact(reply.text), "text"),  # masked, display-only (BR-15)
    }
    counts, ranked = False, None
    if reply.offer is not None and reply.schedule is not None:
        merged = _with(inputs, reply.offer, reply.schedule)  # BR-09: re-audit before anything
        c = compare(ctx.tools, ctx.case_id, merged, code_hidden(merged))
        steps += 4
        r = next(x for x in c.offers if x.offer["offer_id"] == plan.target_offer)
        counts = _COUNTS[move](target, reply.offer, r.audit.comparable)
        after |= {
            p + "revised.version": (int(reply.offer["version"]), "version"),
            p + "revised.comparable": (str(r.audit.comparable).lower(), "bool"),
            p + "revised.flags": (",".join(r.flags) or "none", "codes"),
        }
        if r.priced is not None:
            after |= {
                p + "revised.apr": (r.priced.apr, "rate"),
                p + "revised.total_cost": (r.priced.total_cost, "INR"),
                p + "revised.amount_received": (r.priced.amount_received, "INR"),
            }
        if counts:  # stored so every later comparison includes it (load_offers, ADR 0037)
            after |= {
                p + "revised.offer": (json.dumps(reply.offer, sort_keys=True), "json"),
                p + "revised.schedule": (reply.schedule[1], "text"),
            }
            ranked = (c, merged)
    after[p + "concession_counts"] = (str(counts).lower(), "bool")
    done.append(f"{move}:sent")
    after[NS + "moves"] = (",".join(done), "codes")
    if sum(m.endswith(":sent") for m in done) >= negotiation.MAX_ROUNDS:
        after[NS + "complete"] = ("true", "bool")
    _write(ctx, inputs, after)
    if ranked is not None:  # LW-11 after LW-13: the order now includes the counted concession
        _rerank(ctx, *ranked)
    note = (
        "A revised offer was received and re-audited; the concession counts and the offers "
        "were re-ranked."
        if counts
        else (
            "No concession counts."
            if reply.offer is None
            else "The revision did not pass re-audit."
        )
    )
    what = {
        negotiation.FEE_WAIVER: "Fee-waiver",
        negotiation.RATE_MATCH: "Rate-match",
        negotiation.TENOR_CHANGE: "Tenor-change",
    }[move]
    text = f"Round {round_no}: {what} request sent for {plan.target_offer}. {note}"
    return _done(ctx, Decision.GO, [], steps, text, p + "target")


def _with(inputs: Inputs, offer: Mapping[str, Any], schedule: tuple[str, str]) -> Inputs:
    """The case's offers with ``offer`` in place of its earlier version (in memory only)."""
    offers = tuple(dict(offer) if o["offer_id"] == offer["offer_id"] else o for o in inputs.offers)
    return replace(inputs, offers=offers, schedules={**inputs.schedules, schedule[0]: schedule[1]})


def _rerank(ctx: StageContext, c: Comparison, merged: Inputs) -> None:
    """Every comparison fact of the merged offers, so the ranking, ranks and gate are current.
    Reference rates are unchanged by a round and keep their own lineage."""
    facts = {
        k: v for k, v in facts_for(c, merged).items() if not k.startswith("lw.reference_rate.")
    }
    _write(ctx, merged, facts)


def _write(ctx: StageContext, inputs: Inputs, facts: Mapping[str, tuple[Any, str]]) -> None:
    for key, (value, unit) in facts.items():
        ctx.ledger.put_fact(
            ctx.case_id,
            key,
            value.isoformat() if isinstance(value, date) else value,
            unit=unit,
            source_type="negotiation",
            source_ref=inputs.source_ref,
            produced_by=f"engines.negotiation@{ENGINE_VERSION}",
            input_hash=inputs.input_hash,
        )


def _done(
    ctx: StageContext,
    decision: Decision,
    blockers: list[Blocker],
    steps: int,
    text: str,
    ref: str,
) -> AgentResult:
    evidence = [EvidenceRef(kind="ledger_fact", ref_id=ref)]
    return _result(ctx, decision, blockers, evidence, text, steps, {}, output_ref=ref)


__all__ = ["ENGINE", "FEE_WAIVER_V1", "RATE_MATCH_V1", "TENOR_CHANGE_V1", "negotiate", "prefix"]
