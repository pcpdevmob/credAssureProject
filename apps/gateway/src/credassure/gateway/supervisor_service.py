"""The SupervisorPort the agent routers use (ADR 0005 rule 3, ADR 0006).

Agent routers never touch an agent or the database: they hand the authenticated principal to
this service, which applies the same case policy and job runner as the core /v1 routes.
"""

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from credassure.agents.copilot import agent as copilot
from credassure.agents.copilot import policy
from credassure.core.enums import AgentName, Stage
from credassure.core.errors import ApiErrorCode
from credassure.core.money import format_inr, from_paise, to_paise
from credassure.core.results import AgentResult
from credassure.gateway.deps import Services, own_case, visible_case
from credassure.gateway.jobs import NOT_RUNNABLE, job_view
from credassure.gateway.problems import ProblemError
from credassure.gateway.report import superseded_uploads
from credassure.ledger import reads
from credassure.ledger.session import RunInProgressError, run_in_progress, run_lock, transaction
from credassure.observability.tracing import span
from credassure.security import pii
from credassure.security.auth import Principal, Role
from credassure.tools.registry import authorize_fact

PII_NOTICE = (
    "Personal identifiers ({kinds}) are not accepted in chat; they were removed and not stored "
    "(data-handling policy, DPDP Act 2023)."
)
ABSTAIN = policy.ABSTAIN  # CP-02, exact string
CHAT_NOTICE = (
    "Ask CredAssure drafts answers with a language model from cited sources and this case's "
    "verified figures. It is general information, not legal, tax or credit advice, and it never "
    "approves, accepts or signs anything. Do not enter personal identifiers."
)
MEMORY_TURNS = 4  # scope #2: the last turns of this user in this case


def notice_version() -> str:
    """Scope #40: a changed notice text is a new version that must be acknowledged again."""
    return hashlib.sha256(CHAT_NOTICE.encode()).hexdigest()[:12]


def notice_state(svc: Services, actor: Principal) -> dict[str, Any]:
    version = notice_version()
    with transaction(svc.engine) as s:
        at = reads.notice_acknowledged(s, actor.tenant_id, actor.user_id, version)
    return {"text": CHAT_NOTICE, "version": version, "acknowledged_at": at}


def acknowledge_notice(svc: Services, actor: Principal) -> dict[str, Any]:
    """Record the acknowledgement once per user and notice version (an audit event, OBJ-08)."""
    state = notice_state(svc, actor)
    if state["acknowledged_at"] is None:
        svc.ledger.audit(
            None, "CHAT_NOTICE_ACKNOWLEDGED", {"version": state["version"]}, actor=actor.user_id
        )
        state = notice_state(svc, actor)
    return state


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

    def retry_stage(
        self, actor: Principal, case_id: str, stage: str, *, schedule: Callable[..., Any]
    ) -> dict[str, Any]:
        """Scope #25: an evaluator re-runs one stage of a FAILED case. It is an ordinary stage job
        (run lock, upstream gates, caps, audit, SUP-03), never a way around a gate."""
        if actor.role is not Role.EVALUATOR:
            raise ProblemError(403, "only an evaluator may retry a stage", ApiErrorCode.FORBIDDEN)
        case = visible_case(self.svc, actor, case_id)
        if case.status != "FAILED":
            raise ProblemError(
                409, f"case is {case.status}; only a FAILED case is retried", ApiErrorCode.CONFLICT
            )
        if run_in_progress(self.svc.engine, case.id):
            raise ProblemError(
                409, "a run is in progress on this case", ApiErrorCode.RUN_IN_PROGRESS
            )
        self.svc.ledger.audit(
            case.id, "STAGE_RETRY_REQUESTED", {"stage": stage, "by": actor.user_id}
        )
        job = self.svc.jobs.start(
            case.id,
            stage=Stage(stage),
            idempotency_key=None,
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
            gate_fact = next(f for f in reversed(facts) if f.key == "lw.gate")
            with transaction(self.svc.engine) as s:
                files = reads.case_files(s, case.tenant_id, case.id)
            if changed := sorted(superseded_uploads(gate_fact, files)):
                # UI-05, scope #6: never show a comparison of files that have been replaced.
                return {
                    "gate": None,
                    "source": "stale",
                    "stale": True,
                    "changed": changed,
                    "message": f"New {', '.join(changed)} upload since the last comparison: "
                    "stale, re-run LendWise.",
                    "ranking": [],
                    "offers": [],
                    "negotiation": self.negotiation(actor, case_id),
                }
            view = {
                "gate": stored["lw.gate"],
                "source": "ledger",
                "stale": False,
                **offer_view(stored),
            }
            return view | {"negotiation": self.negotiation(actor, case_id)}
        wc_gate = latest.get("wc.gate")
        gate = wc_gate if wc_gate not in (None, "GO") else None
        preview = self.svc.offer_preview(case.id)
        return {"gate": gate, "source": "preview", "stale": False, **offer_view(preview)}

    def plan(self, actor: Principal, case_id: str) -> dict[str, Any]:
        case = visible_case(self.svc, actor, case_id)
        plan: dict[str, Any] = self.svc.supervisor.plan(case.id).model_dump(mode="json")
        return plan

    def chat(self, actor: Principal, case_id: str, message: str) -> dict[str, Any]:
        """Ask CredAssure (CP-01..03, scope #2, #20, #40). The copilot refuses in code first, then
        answers only from cited passages or code-rendered case facts, and every model answer
        passes the Critic; otherwise the reply is exactly ABSTAIN (CP-02). Only redacted text is
        stored, traced or sent to the model (ONB-06); memory is this user's turns in this case."""
        case = visible_case(self.svc, actor, case_id)
        trace_id = uuid.uuid4().hex
        kinds = sorted({hit.kind for hit in pii.find(message)})  # ONB-06: refuse and redact
        text = pii.redact(message)
        with transaction(self.svc.engine) as s:
            turns = reads.chat_history(s, case.tenant_id, case.id, actor.user_id, MEMORY_TURNS)
            offer_ids = {
                str(json.loads(f.payload_json).get("offer_id") or "")
                for f in reads.case_files(s, case.tenant_id, case.id)
                if f.kind == "offer"
            } - {""}
        with span("chat", trace_id=trace_id, case_id=case.id, message=text[:2000]) as rec:
            reply = copilot.answer(
                text,
                case_id=case.id,
                tools=self.svc.copilot_tools(),
                llm=self.svc.llm,
                history=[(t.role, t.redacted_text) for t in turns],
                offer_ids=offer_ids,
                as_of=self.svc.settings.as_of_date,
            )
            rec.update(  # scope #20 evidence: the chosen tool and whether code accepted it
                tool=reply.tool,
                tool_valid=reply.tool_valid,
                refusal_code=reply.refusal_code,
                injection_flagged=reply.injection_flagged,
                dropped=reply.dropped,
                findings=list(reply.findings),
                abstained=reply.abstained,
            )
        answer = pii.redact(reply.answer)
        chunk_ids = [str(c["chunk_id"]) for c in reply.citations]
        fact_key = None
        if reply.source == "model" and not reply.abstained:
            fact_key = f"cp.answer.{trace_id}"
            authorize_fact(AgentName.COPILOT, fact_key, write=True)  # registry prefixes (#24)
            self.svc.ledger.put_fact(
                case.id,
                fact_key,
                json.dumps({"question": text, "answer": answer}, ensure_ascii=False),
                unit="json",
                source_type="passage" if chunk_ids else "ledger_fact",
                source_ref=",".join(chunk_ids or reply.facts),
                produced_by=f"copilot@{copilot.version()}",
                provenance={"agent": "copilot", "stage": "chat", "trace_id": trace_id},
            )
        self.svc.ledger.chat_turn(
            case.id,
            actor.user_id,
            [("user", text, []), ("assistant", answer, chunk_ids)],
            intent="copilot_question",
            trace_id=trace_id,
        )
        # #40: the notice goes with the reply until this user has acknowledged it; asking the
        # first question counts as the acknowledgement (user decision 2(a), Phase 10).
        notices = [] if notice_state(self.svc, actor)["acknowledged_at"] else [CHAT_NOTICE]
        acknowledge_notice(self.svc, actor)
        if kinds:
            notices.append(PII_NOTICE.format(kinds=", ".join(kinds)))
        out: dict[str, Any] = {
            "answer": answer,
            "citations": [
                {
                    "chunk_id": c["chunk_id"],
                    "doc_id": c["doc_id"],
                    "title": c["title"],
                    "section": c["section_path"],
                    "effective_from": c["effective_from"],
                }
                for c in reply.citations
            ],
            "refused": reply.refused,
            "abstained": reply.abstained,
            "refusal_code": reply.refusal_code,
            "injection_flagged": reply.injection_flagged,
            "ranking": list(reply.ranking) if reply.ranking is not None else None,
            "intent": "copilot_question",
            "trace_id": trace_id,
            "fact_key": fact_key,
            "pii_redacted": bool(kinds),
        }
        if notices:
            out["notice"] = " ".join(notices)
        return out


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
    aprs: dict[str, Decimal] = {}
    for oid, ver in sorted(latest.items()):
        f = {k.rsplit(".", 1)[1]: v for k, v in facts.items() if k.startswith(f"lw.{oid}.v{ver}.")}
        apr = Decimal(f["apr"]) * 100 if "apr" in f else None
        if apr is not None:
            aprs[oid] = apr
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
    # `cheapest_headline_rate` is the lowest APR (full precision; every tied offer is flagged). The
    # name is historical: it is not the lowest nominal rate. The UI only displays it (BR-05).
    lowest = min(aprs.values(), default=None)
    for o in out:
        o["cheapest_headline_rate"] = lowest is not None and aprs.get(str(o["offer_id"])) == lowest
    order = facts.get("lw.ranking", "none")
    return {"ranking": [] if order == "none" else order.split(","), "offers": out}


def _pct(fraction: str) -> str:
    return str((Decimal(fraction) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


PCT = Decimal("0.01")


def _plain(value: Decimal) -> str:
    return format(value.normalize(), "f")
