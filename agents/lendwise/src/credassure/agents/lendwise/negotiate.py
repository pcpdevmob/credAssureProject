"""LendWise negotiation round 1 (design-detail §2.4.7 step 6; LW-12/13, BR-09/10/13/15).

A separate invocation after the comparison. Code picks the target and the verified competing fee
(``engines.negotiation.plan`` over the offers the comparison found comparable), writes them as
ledger facts, and fills the fixed ``fee_waiver_v1`` template from those facts only; no model writes
any part of the message. The message goes to ``verify_claims`` (every figure must equal a ledger
fact; no acceptance, approval or urgency wording) before the simulated lender sees it. The lender's
reply is scanned for injected instructions and never reused as text. A revised version is
re-audited and re-priced, and only then are the concession and the revised figures written.
Nothing here accepts, signs or submits an offer (BR-13).
"""

from decimal import Decimal
from string import Template
from typing import Any

from credassure.agents.lendwise.agent import (
    ENGINE,
    ENGINE_VERSION,
    Comparison,
    Inputs,
    _result,
    code_hidden,
    compare,
)
from credassure.core.enums import Decision
from credassure.core.findings import CriticFinding
from credassure.core.money import format_inr
from credassure.core.ports import StageContext
from credassure.core.results import AgentResult, Blocker, EvidenceRef
from credassure.engines import negotiation
from credassure.security.injection import scan

TEMPLATE_ID = "fee_waiver_v1"
FEE_WAIVER_V1 = Template(
    "Dear $lender_name,\n\n"
    "Thank you for offer $offer_id. Its processing fee is $current_fee. "
    "Another lender's comparable offer for this proposal carries a processing fee of "
    "$competing_fee.\n\n"
    "We request that you waive or reduce the processing fee on offer $offer_id. This is a "
    "request for a revised offer only; the business will choose its lender separately.\n"
)
NS = "lw.negotiation."


def _fee(value: str, unit: str) -> str:
    """A fee from the ledger in words, exactly as stored: a share of the loan amount ("rate",
    shown as a percentage) or a fixed amount in rupees ("INR")."""
    if unit == "INR":
        return format_inr(Decimal(value))
    pct = (Decimal(value) * 100).normalize()
    return f"{format(pct, 'f')}% of the loan amount"


def _unit(basis: str) -> str:
    return "rate" if basis == "pct_of_principal" else "INR"


def negotiate(ctx: StageContext) -> AgentResult:
    """One fee-waiver round. Decision GO = the round ran (or no verified competitor exists);
    NO_GO = the message failed verification and was not sent."""
    steps = 1
    inputs: Inputs = ctx.tools.call("load_offers", ctx.case_id)
    if ctx.ledger.get(ctx.case_id, "lw.gate") is None:
        q = "Can you run the lender comparison first?"
        return _result(ctx, Decision.NEEDS_INPUT, [], [], q, steps, {}, question=q)
    comparable = [
        o
        for o in inputs.offers
        if ctx.ledger.get(ctx.case_id, f"lw.{o['offer_id']}.v{o['version']}.comparable") == "true"
    ]
    plan = negotiation.plan(comparable)
    facts: dict[str, tuple[Any, str]] = {}
    if plan is None:  # BR-10: no verified competing fee, so no message
        facts[NS + "target"] = ("none", "offer_id")
        facts[NS + "status"] = ("none", "enum")
        _write(ctx, inputs, facts)
        return _done(ctx, Decision.GO, [], steps, "No verified competing fee; no message sent.")
    target = next(o for o in comparable if o["offer_id"] == plan.target_offer)
    facts |= {
        NS + "target": (plan.target_offer, "offer_id"),
        NS + "template": (TEMPLATE_ID, "id"),
        NS + "current_fee": (plan.current_fee, _unit(plan.current_basis)),
        NS + "competing_fee": (plan.competing_fee, _unit(plan.competing_basis)),
        NS + "competing_offer": (plan.competing_offer, "offer_id"),
    }
    _write(ctx, inputs, facts)

    def get(key: str) -> str:
        return ctx.ledger.get(ctx.case_id, NS + key) or ""

    message = FEE_WAIVER_V1.substitute(  # LW-12: every slot comes back from the ledger
        lender_name=target["lender_name"],
        offer_id=get("target"),
        current_fee=_fee(get("current_fee"), _unit(plan.current_basis)),
        competing_fee=_fee(get("competing_fee"), _unit(plan.competing_basis)),
    )
    keys = [NS + "current_fee", NS + "competing_fee"]  # the only figures the message may carry
    findings: list[CriticFinding] = ctx.tools.call(
        "verify_claims", ctx.case_id, {"text": message, "keys": keys, "stage": "lendwise"}
    )
    steps += 1
    if findings:  # the Verification Critic (VER-01/03): blocked, never sent
        blockers = [Blocker(code=f.code, message=f.message) for f in findings[:5]]
        _write(ctx, inputs, {NS + "status": ("blocked", "enum")})
        return _done(ctx, Decision.NO_GO, blockers, steps, "The message failed verification.")
    schedule = inputs.schedules[inputs.schedule_id(target)]
    reply = ctx.tools.call(
        "lender_send_template",
        ctx.case_id,
        {
            "lender_id": target["lender_id"],
            "template_id": TEMPLATE_ID,
            "message": message,
            "offer": target,
            "schedule": schedule,
        },
    )
    steps += 1
    # BR-15: the reply is data; a planted instruction is only recorded (A5: scanner off)
    flags = [] if ctx.ablation == "A5" else scan(reply.text)
    after: dict[str, tuple[Any, str]] = {
        NS + "message": (message, "text"),
        NS + "status": ("sent", "enum"),
        NS + "reply_flags": (",".join(flags) or "none", "codes"),
    }
    counts = False
    if reply.offer is not None and reply.schedule is not None:
        revised = _reaudit(ctx, inputs, reply.offer, reply.schedule)  # BR-09 before anything
        steps += 4
        r = revised.offers[0]
        counts = negotiation.concession_counts(target, reply.offer, r.audit.comparable)
        after |= {
            NS + "revised.version": (int(reply.offer["version"]), "version"),
            NS + "revised.comparable": (str(r.audit.comparable).lower(), "bool"),
            NS + "revised.flags": (",".join(r.flags) or "none", "codes"),
        }
        if r.priced is not None:
            after |= {
                NS + "revised.apr": (r.priced.apr, "rate"),
                NS + "revised.total_cost": (r.priced.total_cost, "INR"),
                NS + "revised.amount_received": (r.priced.amount_received, "INR"),
            }
    after[NS + "concession_counts"] = (str(counts).lower(), "bool")
    _write(ctx, inputs, after)
    note = (
        "A revised offer was received and re-audited; the concession counts."
        if counts
        else (
            "No concession counts."
            if reply.offer is None
            else "The revision did not pass re-audit."
        )
    )
    return _done(
        ctx, Decision.GO, [], steps, f"Fee-waiver request sent for {plan.target_offer}. {note}"
    )


def _reaudit(
    ctx: StageContext, inputs: Inputs, offer: dict[str, Any], schedule: tuple[str, str]
) -> Comparison:
    """LW-13: the revised version alone through the same audit, pricing and fit tools."""
    revised = Inputs(
        (offer,),
        {schedule[0]: schedule[1]},
        inputs.enterprise_class,
        inputs.position,
        inputs.sources,
        inputs.reference_rates,
    )
    return compare(ctx.tools, ctx.case_id, revised, code_hidden(revised))


def _write(ctx: StageContext, inputs: Inputs, facts: dict[str, tuple[Any, str]]) -> None:
    for key, (value, unit) in facts.items():
        ctx.ledger.put_fact(
            ctx.case_id,
            key,
            value,
            unit=unit,
            source_type="negotiation",
            source_ref=inputs.source_ref,
            produced_by=f"engines.negotiation@{ENGINE_VERSION}",
            input_hash=inputs.input_hash,
        )


def _done(
    ctx: StageContext, decision: Decision, blockers: list[Blocker], steps: int, text: str
) -> AgentResult:
    evidence = [EvidenceRef(kind="ledger_fact", ref_id=NS + "target")]
    return _result(ctx, decision, blockers, evidence, text, steps, {}, output_ref=NS + "target")


__all__ = ["ENGINE", "FEE_WAIVER_V1", "negotiate"]
