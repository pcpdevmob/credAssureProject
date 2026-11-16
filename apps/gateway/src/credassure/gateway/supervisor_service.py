"""The SupervisorPort the agent routers use (ADR 0005 rule 3, ADR 0006).

Agent routers never touch an agent or the database: they hand the authenticated principal to
this service, which applies the same case policy and job runner as the core /v1 routes.
"""

import re
import uuid
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from credassure.core.enums import Stage
from credassure.core.errors import ApiErrorCode
from credassure.core.money import format_inr, from_paise, to_paise
from credassure.core.results import AgentResult
from credassure.gateway.deps import Services, own_case, visible_case
from credassure.gateway.jobs import NOT_RUNNABLE, job_view
from credassure.gateway.problems import ProblemError
from credassure.ledger import reads
from credassure.ledger.session import RunInProgressError, run_in_progress, run_lock, transaction
from credassure.observability.tracing import span
from credassure.security import pii
from credassure.security.auth import Principal

PII_NOTICE = (
    "Personal identifiers ({kinds}) are not accepted in chat; they were removed and not stored "
    "(data-handling policy, DPDP Act 2023)."
)
UNAVAILABLE = (
    "The copilot is unavailable: cited, Critic-checked answers arrive with the copilot (Phase 9e)."
)


class SupervisorService:
    def __init__(self, svc: Services) -> None:
        self.svc = svc

    def start_run(
        self,
        actor: Principal,
        case_id: str,
        *,
        stage: str | None,
        idempotency_key: str | None,
        schedule: Callable[..., Any],
    ) -> dict[str, Any]:
        case = own_case(self.svc, actor, case_id)
        if (
            idempotency_key is not None
        ):  # a replay returns the original job, whatever happened since
            with transaction(self.svc.engine) as s:
                seen = reads.job_by_key(s, case.tenant_id, case.id, idempotency_key)
            if seen is not None:
                replay: dict[str, Any] = job_view(seen)
                return replay
        if case.status in NOT_RUNNABLE:
            raise ProblemError(409, f"case is {case.status}; nothing to run", ApiErrorCode.CONFLICT)
        if run_in_progress(self.svc.engine, case.id):  # fail fast; the job would only fail later
            raise ProblemError(
                409, "a run is in progress on this case", ApiErrorCode.RUN_IN_PROGRESS
            )
        job = self.svc.jobs.start(
            case.id,
            stage=Stage(stage) if stage else None,
            idempotency_key=idempotency_key,
            actor=actor.user_id,
            schedule=schedule,
        )
        view: dict[str, Any] = job_view(job)
        return view

    def latest_result(
        self, actor: Principal, case_id: str, stage: str | None
    ) -> AgentResult | None:
        case = visible_case(self.svc, actor, case_id)
        with transaction(self.svc.engine) as s:
            runs = [
                r
                for r in reads.stage_runs(s, case.tenant_id, case.id)
                if r.result_json and (stage is None or r.stage == stage)
            ]
        latest = runs[-1].result_json if runs else None
        return AgentResult.model_validate_json(latest) if latest else None

    def fact(self, actor: Principal, case_id: str, key: str) -> str | None:
        """Latest value of one ledger fact, under the same case policy as every read."""
        case = visible_case(self.svc, actor, case_id)
        with transaction(self.svc.engine) as s:
            found = reads.get_latest(s, case.tenant_id, case.id, key)
        return None if found is None else found.value_text

    def negotiate(self, actor: Principal, case_id: str) -> dict[str, Any]:
        """LW-12/13: one fee-waiver round, a separate invocation through the Supervisor (caps,
        case pinning, audit). The preparer only; one sent request per case, under the case run
        lock so two calls cannot both send; never accepts an offer."""
        case = own_case(self.svc, actor, case_id)
        # The round changes neither the funding amount nor the route, so it may run while the
        # proposal awaits approval; a decided case is closed.
        if case.status in ("APPROVED", "REJECTED"):
            raise ProblemError(409, f"case is {case.status}; closed", ApiErrorCode.CONFLICT)
        from credassure.agents.lendwise.negotiate import negotiate

        try:
            with run_lock(self.svc.engine, case.tenant_id, case.id, uuid.uuid4().hex):
                if self.fact(actor, case_id, "lw.negotiation.status") == "sent":
                    raise ProblemError(
                        409, "the negotiation round has already run", ApiErrorCode.CONFLICT
                    )
                result = self.svc.supervisor.invoke_extra(
                    case.id, Stage.LENDWISE, negotiate, "negotiate"
                )
        except RunInProgressError as exc:
            raise ProblemError(
                409, "a run is in progress on this case", ApiErrorCode.RUN_IN_PROGRESS
            ) from exc
        return {"decision": result.decision.value, **self.negotiation(actor, case_id)}

    def negotiation(self, actor: Principal, case_id: str) -> dict[str, Any]:
        """The round as stored facts: what was asked, and a concession only after re-audit."""
        case = visible_case(self.svc, actor, case_id)
        with transaction(self.svc.engine) as s:
            facts = reads.list_for_case(s, case.tenant_id, case.id)
        latest = {x.key.removeprefix("lw.negotiation."): x for x in facts}
        f = {k: x.value_text for k, x in latest.items()}
        target = f.get("target")
        if target in (None, "none"):
            return {
                "target_offer": None,
                "competing_fee_pct": None,
                "concession_counts": False,
                "message": "",
                "status": f.get("status"),
                "revised": None,
            }
        revised = None
        if "revised.version" in f:
            apr, cost, flags = f.get("revised.apr"), f.get("revised.total_cost"), f["revised.flags"]
            revised = {
                "version": int(f["revised.version"]),
                "comparable": f.get("revised.comparable") == "true",
                "flags": [] if flags == "none" else flags.split(","),
                "apr_pct": None if apr is None else _pct(apr),
                "total_cost": None if cost is None else _money(to_paise(Decimal(cost))),
            }
        rate = latest["competing_fee"].unit == "rate"
        return {
            "target_offer": target,
            "competing_fee_pct": _plain(Decimal(f["competing_fee"]) * 100) if rate else None,
            "competing_fee": _money(to_paise(Decimal(f["competing_fee"]))) if not rate else None,
            "concession_counts": f.get("concession_counts") == "true",
            "message": f.get("message", ""),
            "status": f.get("status"),
            "revised": revised,
        }

    def offers(self, actor: Principal, case_id: str) -> dict[str, Any]:
        """The offer comparison. After the LendWise stage: its stored facts. Before it, while
        the funding stage is not GO, a read-only audit preview (no affordability, no ranking)."""
        case = visible_case(self.svc, actor, case_id)
        with transaction(self.svc.engine) as s:
            facts = reads.list_for_case(s, case.tenant_id, case.id)
        latest = {f.key: f.value_text for f in facts}  # versions ascend per key
        stored = {k: v for k, v in latest.items() if k.startswith("lw.")}
        if "lw.gate" in stored:
            view = {"gate": stored["lw.gate"], "source": "ledger", **offer_view(stored)}
            return view | {"negotiation": self.negotiation(actor, case_id)}
        wc_gate = latest.get("wc.gate")
        gate = wc_gate if wc_gate not in (None, "GO") else None
        preview = self.svc.offer_preview(case.id)
        return {"gate": gate, "source": "preview", **offer_view(preview)}

    def plan(self, actor: Principal, case_id: str) -> dict[str, Any]:
        case = visible_case(self.svc, actor, case_id)
        plan: dict[str, Any] = self.svc.supervisor.plan(case.id).model_dump(mode="json")
        return plan

    def chat(self, actor: Principal, case_id: str, message: str) -> dict[str, Any]:
        """Placeholder copilot (Phase 9e). No model text reaches the user before the Critic can
        check it (CP-01, VER-01), so this returns a fixed notice whether the model is on or off."""
        case = visible_case(self.svc, actor, case_id)
        trace_id = uuid.uuid4().hex
        kinds = sorted({hit.kind for hit in pii.find(message)})  # ONB-06: refuse and redact
        with span(  # E11 N1: the id names a span; only the redacted text is ever recorded
            "chat", trace_id=trace_id, case_id=case.id, message=pii.redact(message)[:2000]
        ):
            pass
        reply: dict[str, Any] = {
            "answer": UNAVAILABLE,
            "citations": [],
            "intent": "copilot_question",
            "trace_id": trace_id,
            "pii_redacted": bool(kinds),
        }
        if kinds:
            reply["notice"] = PII_NOTICE.format(kinds=", ".join(kinds))
        return reply


def approval_warnings(facts: Any) -> list[str]:
    """APR-04 evidence for the approver (ADR 0023, BR-09), from ledger fact rows (all versions):
    ``negotiation_in_progress`` — a sent round is newer than the comparison the case was verified
    and routed on, so its revision is not in the ranking; ``revised_offer_not_reaudited`` — a
    revised version arrived but did not pass re-audit, so no concession counts."""
    latest: dict[str, Any] = {}
    for f in facts:
        if f.key not in latest or f.version > latest[f.key].version:
            latest[f.key] = f
    status, gate = latest.get("lw.negotiation.status"), latest.get("lw.gate")
    out = []
    if status is not None and status.value_text == "sent":
        if gate is None or status.created_at > gate.created_at:
            out.append("negotiation_in_progress")
        counts = latest.get("lw.negotiation.concession_counts")
        if "lw.negotiation.revised.version" in latest and (
            counts is None or counts.value_text != "true"
        ):
            out.append("revised_offer_not_reaudited")
    return out


def _money(paise: int) -> dict[str, Any]:
    return {"paise": paise, "display": format_inr(from_paise(paise))}


_LW_MONEY = ("amount_received", "total_repayment", "total_cost", "gst", "cgst", "sgst")


def offer_view(facts: dict[str, str]) -> dict[str, Any]:
    """lw.* facts -> the comparison (UI-05): each offer at its latest version, money as
    {paise, display}, APR as a percentage with two decimals."""
    latest: dict[str, int] = {}
    for key in facts:
        m = re.match(r"^lw\.(OF-[A-Za-z0-9-]+)\.v(\d+)\.", key)
        if m:
            latest[m[1]] = max(latest.get(m[1], 0), int(m[2]))
    out = []
    for oid, ver in sorted(latest.items()):
        f = {k.rsplit(".", 1)[1]: v for k, v in facts.items() if k.startswith(f"lw.{oid}.v{ver}.")}
        apr = Decimal(f["apr"]) * 100 if "apr" in f else None
        out.append(
            {
                "offer_id": oid,
                "version": ver,
                "flags": [] if f.get("flags", "none") == "none" else f["flags"].split(","),
                "comparable": f.get("comparable") == "true",
                "affordable": None if "affordable" not in f else f["affordable"] == "true",
                "rank": int(f["rank"]) if "rank" in f else None,
                "apr_pct": None
                if apr is None
                else str(apr.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                **{k: _money(to_paise(Decimal(f[k]))) if k in f else None for k in _LW_MONEY},
            }
        )
    order = facts.get("lw.ranking", "none")
    return {"ranking": [] if order == "none" else order.split(","), "offers": out}


def _pct(fraction: str) -> str:
    return str((Decimal(fraction) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


PCT = Decimal("0.01")


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")
