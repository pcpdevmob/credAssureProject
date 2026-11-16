"""Supervisor workflow: a LangGraph state graph whose edges are decided by code (SUP-01..08).

    START → next → <first plan stage not GO> → next → … → routing → approval (interrupt) → END
    A paused, failed or single-stage run sets `outcome` and ends; resume re-enters at `next`, so
    only the blocked stage runs again (SUP-06). A return from the approver clears that stage on.

The model never decides order, gates or routes (BR-11). Agents are injected by the gateway and
never import each other (ADR 0005, ADR 0009); case_id is always the run's own (SUP-08).
"""

import contextvars
import json
import logging
import re
import threading
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, NotRequired, TypedDict, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import ValidationError

from credassure.agents.supervisor import __version__
from credassure.core.blockers import BlockerCode, BlockerEffect, blocker_effect
from credassure.core.budget import stage_budget
from credassure.core.enums import AgentName, Decision, Stage
from credassure.core.errors import (
    ApiErrorCode,
    BudgetExceeded,
    LLMError,
    LLMTimeout,
    ModelUnavailable,
    NoPendingApproval,
)
from credassure.core.findings import CriticFinding, FindingSeverity
from credassure.core.plan import FIXED_STAGES, Plan
from credassure.core.ports import (
    ClockPort,
    LedgerPort,
    LLMPort,
    StageAgent,
    StageContext,
    SupervisorStore,
    ToolPort,
)
from credassure.core.prompts import prompt_sha, prompt_version
from credassure.core.prompts import registry as prompts
from credassure.core.results import AgentResult, Blocker
from credassure.engines.routing import route as route_amount
from credassure.observability.tracing import span
from credassure.security.pii import redact
from credassure.tools.registry import RegistryError, authorize_fact
from credassure.tools.runner import LoopDetected

Recheck = Callable[[AgentResult, LedgerPort], list[Blocker]]
_log = logging.getLogger("credassure.supervisor")
MAX_REPAIRS = 2  # SUP-04: an invalid result is re-requested at most twice
AMOUNT_KEY = "wc.recommended_amount"  # rupees, Decimal text (the threshold applies to it, Q-02)
RETURNABLE = (Stage.ONBOARDING, Stage.WORKING_CAPITAL, Stage.LENDWISE)  # APR-05 named stages
MAX_REGENERATIONS = 2  # VER-05: then the template
MAX_REROUTES = 2  # ARCHITECTURE §6.3: Critic -> stage at most twice per run, then pause
FINDINGS_KEY = "ver.findings"  # the Critic stage's findings (JSON list of CriticFinding)
WITHHELD = "The explanation failed verification and is withheld; the figures stand."
Critic = Callable[[AgentResult], list[CriticFinding]]
A4_PROMPT = "sup_gate_a4"  # ablation A4 only


class StageCancelledError(RuntimeError):
    """The stage timed out (scope #23): its orphan thread may not call the model, tools or
    ledger again, so nothing it does after the timeout is written."""


class InvalidReturnStageError(ValueError):
    """A return must name one of RETURNABLE (N1: never a silent no-op)."""


@dataclass
class RunOutcome:
    # PAUSED | IN_PROGRESS | AWAITING_APPROVAL | HELD | FAILED | APPROVED | REJECTED | RETURNED
    # | ABANDONED (the run lost its lock and stopped before the next stage)
    status: str
    stage: Stage | None = None
    question: str | None = None
    results: dict[Stage, AgentResult] = field(default_factory=dict)
    reason: str | None = None  # a blocker code, e.g. SUP_ROUTE_HELD on a HELD route


class _State(TypedDict):
    case_id: str
    trace_id: str  # one Langfuse trace per run; decide() reuses it (BRD §14)
    stages: list[str]
    target: str | None
    outcome: dict[str, Any] | None
    results: NotRequired[dict[str, dict[str, Any]]]  # kept across runs by the checkpointer
    reroutes: NotRequired[int]  # Critic -> stage re-routes in this run (MAX_REROUTES)
    pending: NotRequired[dict[str, list[dict[str, Any]]]]  # stage -> Critic findings to fix


def _same_case(bound: str, case_id: str) -> None:
    """SUP-08, BR-14: a stage reaches only the case the Supervisor injected."""
    if case_id != bound:
        raise RegistryError(ApiErrorCode.CASE_REQUIRED)


def _check(cancel: threading.Event) -> None:
    if cancel.is_set():
        raise StageCancelledError("stage timed out")


class _TracedLLM:
    """E11 M1: every model call an agent makes is a span in the run's trace (BRD §14), carrying
    the prompt version and hash (scope #36). Refused once the stage has timed out (#23)."""

    def __init__(self, llm: LLMPort, case_id: str, stage: Stage, cancel: threading.Event) -> None:
        self._llm, self._case_id, self._stage, self._cancel = llm, case_id, stage, cancel
        self.circuit_state = getattr(llm, "circuit_state", "closed")
        self.versions: dict[str, str] = {}

    def complete(
        self, prompt: str, *, name: str = "default", json_schema: Mapping[str, Any] | None = None
    ) -> str:
        _check(self._cancel)
        self.versions[name] = version = prompt_version(name)
        with span(
            "llm",
            prompt=name,
            prompt_version=version,
            prompt_sha=prompt_sha(name),
            case_id=self._case_id,
            stage=self._stage.value,
            input=redact(prompt)[:2000],  # masked I/O on the span (Phase 6, NFR-07)
        ) as record:
            reply = self._llm.complete(prompt, name=name, json_schema=json_schema)
            record["output"] = redact(reply)[:2000]
            return reply


class _GuardedLedger:
    """The stage's ledger: only the agent's registry prefixes (scope #24), and writes are
    refused once the stage has timed out (#23)."""

    def __init__(
        self, ledger: LedgerPort, cancel: threading.Event, agent: AgentName, case_id: str
    ) -> None:
        self._ledger, self._cancel, self._agent, self._case = ledger, cancel, agent, case_id

    def get(self, case_id: str, key: str) -> str | None:
        _same_case(self._case, case_id)
        authorize_fact(self._agent, key)
        return self._ledger.get(case_id, key)

    def put_fact(
        self,
        case_id: str,
        key: str,
        value: Decimal | int | str,
        *,
        unit: str,
        source_type: str,
        source_ref: str,
        produced_by: str,
        input_hash: str | None = None,
    ) -> int:
        _check(self._cancel)
        _same_case(self._case, case_id)
        authorize_fact(self._agent, key, write=True)
        if key.endswith("narrative") and isinstance(value, str):
            value = redact(value)  # NFR-07: free text is redacted before it is stored
        return self._ledger.put_fact(
            case_id,
            key,
            value,
            unit=unit,
            source_type=source_type,
            source_ref=source_ref,
            produced_by=produced_by,
            input_hash=input_hash,
        )


class _AuditedTools:
    """E11 M2, design-detail §2.3: every tool call is a span and an audit event."""

    def __init__(
        self,
        tools: ToolPort,
        store: SupervisorStore,
        agent: AgentName,
        trace_id: str,
        cancel: threading.Event,
        case_id: str,
    ) -> None:
        self._tools, self._store, self._agent, self._trace_id = tools, store, agent, trace_id
        self._cancel, self._case = cancel, case_id

    def call(self, name: str, case_id: str, args: Mapping[str, Any] | None = None) -> Any:
        _check(self._cancel)
        _same_case(self._case, case_id)
        error: str | None = None
        try:
            with span("tool", tool=name, agent=self._agent.value, case_id=case_id):
                return self._tools.call(name, case_id, args)
        except Exception as exc:
            error = type(exc).__name__
            raise
        finally:  # arguments stay out of the audit log: the tool's own facts carry provenance
            self._store.audit(
                case_id,
                "TOOL_CALLED",
                {
                    "agent": self._agent.value,
                    "tool": name,
                    "trace_id": self._trace_id,
                    "error": error,
                    "after_timeout": self._cancel.is_set(),  # an orphan's event, tagged (#23)
                },
            )


def _evidence_and_gate_check(result: AgentResult, ledger: LedgerPort) -> list[Blocker]:
    """Skeleton re-check: no gate blocker on a GO, and every cited ledger fact exists."""
    failed = [b for b in result.blockers if blocker_effect(b.code) is BlockerEffect.GATE]
    for ref in result.evidence:
        if ref.kind == "ledger_fact" and ledger.get(result.case_id, ref.ref_id) is None:
            failed.append(
                Blocker(
                    code=BlockerCode.SUP_RECHECK_MISMATCH,
                    message=f"evidence fact {ref.ref_id} is not in the ledger",
                )
            )
    return failed


def default_rechecks() -> dict[Stage, Recheck]:
    """Phases 9a-9c replace these with the engines' own recomputation per stage (SUP-05)."""
    return {stage: _evidence_and_gate_check for stage in FIXED_STAGES}


class Supervisor:
    def __init__(
        self,
        *,
        agents: Mapping[Stage, StageAgent],
        store: SupervisorStore,
        ledger: LedgerPort,
        tools: Callable[[AgentName], ToolPort],
        llm: LLMPort | None,
        clock: ClockPort,
        checkpointer: BaseCheckpointSaver[Any],
        tenant_id: str = "default",
        rechecks: Mapping[Stage, Recheck] | None = None,
        max_steps: int = 10,
        token_cap: int = 6000,
        planner_mode: Literal["fixed", "llm_proposes"] = "fixed",
        ablation: str | None = None,
        boundary_rule: Literal["hold", "director", "vp"] = "hold",
        stage_timeout: float = 300.0,
        critic: Critic | None = None,
    ) -> None:
        self.agents, self.store, self.ledger = agents, store, ledger
        self.tools, self.llm, self.clock = tools, llm, clock
        self.tenant_id = tenant_id
        self.rechecks = default_rechecks() if rechecks is None else dict(rechecks)
        self.max_steps, self.token_cap = max_steps, token_cap
        self.stage_timeout = stage_timeout  # scope #23: 5 min per stage
        self.planner_mode, self.ablation = planner_mode, ablation
        self.boundary_rule: Literal["hold", "director", "vp"] = boundary_rule
        self.critic = critic  # injected by the gateway (agents never import the Critic)
        self.graph = self._build().compile(checkpointer=checkpointer)
        # One run per case at a time (run lock), so a per-case cancel hook is safe to share.
        self._cancelled: dict[str, Callable[[], bool]] = {}

    # ---- public API -------------------------------------------------------------------------
    def plan(self, case_id: str, trace_id: str | None = None) -> Plan:
        """Visible plan (scope #19). The model may propose; code accepts only the fixed order."""
        plan = Plan(case_id=case_id)
        with span(
            "plan",
            trace_id=trace_id,
            case_id=case_id,
            mode=plan.mode,
            stages=[st.value for st in plan.stages],
            accepted=self.planner_mode != "llm_proposes",
        ) as record:  # S1: the model call happens inside the plan span
            if self.planner_mode == "llm_proposes" and self.llm is not None:
                prompt = prompts()["sup_plan"].render(
                    case_id=case_id, stages=", ".join(st.value for st in FIXED_STAGES)
                )
                try:
                    with span(
                        "llm",
                        prompt="sup_plan",
                        prompt_version=prompt_version("sup_plan"),
                        prompt_sha=prompt_sha("sup_plan"),
                        case_id=case_id,
                    ):
                        proposed = json.loads(self.llm.complete(prompt, name="sup_plan"))
                    if isinstance(proposed, list) and tuple(proposed) == tuple(
                        st.value for st in FIXED_STAGES
                    ):
                        plan = Plan(case_id=case_id, mode="llm_proposes")
                        record.update(mode=plan.mode, accepted=True)
                except (json.JSONDecodeError, TypeError, ValueError, LLMError):
                    pass  # model down or wrong: the fixed plan stands
            return plan

    def run(
        self,
        case_id: str,
        *,
        stage: Stage | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> RunOutcome:
        """Run the plan from the first stage that is not GO. `cancelled()` is checked before each
        stage: a run that lost its lock stops writing (ADR 0007 §4) and ends ABANDONED."""
        self._cancelled[case_id] = cancelled or (lambda: False)
        try:
            return self._run(case_id, stage)
        finally:
            self._cancelled.pop(case_id, None)

    def _run(self, case_id: str, stage: Stage | None) -> RunOutcome:
        config = self._config(case_id)
        snapshot = self.graph.get_state(config)
        if snapshot.next:  # waiting on the approver: nothing to run until a decision arrives
            return self._outcome(snapshot.values)
        trace_id = uuid.uuid4().hex  # 32 lowercase hex: a valid Langfuse/W3C trace id
        plan = self.plan(case_id, trace_id)
        state: _State = {
            "case_id": case_id,
            "trace_id": trace_id,
            "stages": [s.value for s in plan.stages],
            "target": stage.value if stage else None,
            "outcome": None,
            "reroutes": 0,
            "pending": {},
        }
        if "results" not in snapshot.values:
            state["results"] = {}
        return self._outcome(self.graph.invoke(state, config))

    def decide(
        self,
        case_id: str,
        *,
        decision: Literal["approve", "reject", "return"],
        return_stage: Stage | None = None,
    ) -> RunOutcome:
        """Resume the approval interrupt. The ledger already recorded the decision (APR-04).

        A return is validated first (N1). A return with no pending interrupt fails closed (S1):
        the case is FAILED with SUP_RETURN_NO_PENDING_APPROVAL, never silently left GO.
        """
        if decision == "return" and return_stage not in RETURNABLE:
            raise InvalidReturnStageError(
                f"return_stage must be one of {[s.value for s in RETURNABLE]}"
            )
        config = self._config(case_id)
        if not self.graph.get_state(config).next:
            if decision == "return" and return_stage is not None:
                self.fail_return(case_id, return_stage)
            raise NoPendingApproval(f"case {case_id} is not waiting for a decision")
        resume = {
            "decision": decision,
            "return_stage": return_stage.value if return_stage else None,
        }
        return self._outcome(self.graph.invoke(Command(resume=resume), config))

    def awaiting_decision(self, case_id: str) -> bool:
        return bool(self.graph.get_state(self._config(case_id)).next)

    def fail_return(self, case_id: str, return_stage: Stage) -> None:
        """S1: a return the graph cannot apply. Record the blocker, FAIL the case, audit it."""
        code = BlockerCode.SUP_RETURN_NO_PENDING_APPROVAL
        trace_id = uuid.uuid4().hex
        run_id = self.store.stage_started(case_id, return_stage.value, trace_id)
        result = self._error(
            case_id, return_stage, trace_id, code, "return received with no pending approval"
        )
        self.store.stage_finished(run_id, result)
        self.store.set_state(case_id, status="FAILED", current_stage=return_stage.value)
        self.store.audit(
            case_id, "RETURN_REJECTED", {"code": code.value, "return_stage": return_stage.value}
        )

    # ---- graph ------------------------------------------------------------------------------
    def _build(self) -> StateGraph[_State]:
        g: StateGraph[_State] = StateGraph(_State)
        names = [s.value for s in FIXED_STAGES]
        for name in names:
            g.add_node(name, cast(Any, self._stage_node(Stage(name))))
        g.add_node("upstream_not_go", self._upstream_not_go)
        g.add_node("routing", self._routing)
        g.add_node("approval", self._approval)
        targets = [*names, "upstream_not_go", "routing", END]
        g.add_conditional_edges(START, self._next, targets)
        for name in names:
            g.add_conditional_edges(name, self._next, targets)
        g.add_edge("upstream_not_go", END)
        g.add_conditional_edges(
            "routing", lambda s: END if s["outcome"]["status"] == "FAILED" else "approval"
        )
        g.add_edge("approval", END)
        return g

    def _next(self, state: _State) -> str:
        """Code decides the next node: the first stage in the plan that is not GO (SUP-01, -06)."""
        if state.get("outcome"):
            return END
        results, stages, target = state.get("results", {}), state["stages"], state.get("target")
        if target is not None:
            upstream = stages[: stages.index(target)]
            if any(results.get(s, {}).get("decision") != Decision.GO for s in upstream):
                return "upstream_not_go"  # SUP-03
            return target
        for name in stages:
            if results.get(name, {}).get("decision") != Decision.GO:
                return name
        return "routing"

    def _stage_node(self, stage: Stage) -> Callable[[_State], dict[str, Any]]:
        def node(state: _State) -> dict[str, Any]:
            if self._cancelled.get(state["case_id"], lambda: False)():
                return {"outcome": {"status": "ABANDONED", "stage": stage.value, "question": None}}
            pending = dict(state.get("pending") or {})
            fix = tuple(CriticFinding.model_validate(f) for f in pending.pop(stage.value, []))
            result = self._invoke(state["case_id"], stage, state["trace_id"], fix)
            results = {**state.get("results", {}), stage.value: result.model_dump(mode="json")}
            outcome: dict[str, Any] | None = None
            if stage is Stage.CRITIC and result.decision is Decision.NO_GO:
                back = self._reroute(state, result)
                if back is not None:
                    return back
            if result.decision is Decision.ERROR:
                outcome = self._stop(result, "FAILED")
            elif result.decision is not Decision.GO:
                outcome = self._stop(result, "PAUSED")
            elif state.get("target") is not None:
                outcome = {"status": "IN_PROGRESS", "stage": stage.value, "question": None}
            return {"results": results, "outcome": outcome, "pending": pending}

        return node

    def _reroute(self, state: _State, result: AgentResult) -> dict[str, Any] | None:
        """ARCHITECTURE §6.3: a Critic finding reopens the earliest offending stage (and clears
        the stages after it) with the findings to fix; at most MAX_REROUTES, then pause."""
        case_id, done = state["case_id"], state.get("reroutes", 0)
        try:
            found = [
                CriticFinding.model_validate(f)
                for f in json.loads(self.ledger.get(case_id, FINDINGS_KEY) or "[]")
            ]
        except (ValueError, ValidationError):
            return None  # unreadable findings: the NO_GO stands and the case pauses
        stages = state["stages"]
        upstream = stages[: stages.index(Stage.CRITIC.value)]
        targets = [
            f.target_stage.value
            for f in found
            if f.target_stage is not None and f.target_stage.value in upstream
        ]
        if not targets or done >= MAX_REROUTES:
            return None
        back = min(targets, key=stages.index)
        self.store.audit(
            case_id,
            "CRITIC_REROUTE",
            {"stage": back, "codes": sorted({f.code.value for f in found}), "attempt": done + 1},
        )
        keep = stages[: stages.index(back)]
        results = {k: v for k, v in state.get("results", {}).items() if k in keep}
        fix = [
            f.model_dump(mode="json")
            for f in found
            if f.target_stage is not None and f.target_stage.value == back
        ]
        return {  # a targeted run becomes a resume: the plan continues from the reopened stage
            "results": results,
            "outcome": None,
            "target": None,
            "reroutes": done + 1,
            "pending": {**(state.get("pending") or {}), back: fix},
        }

    def _upstream_not_go(self, state: _State) -> dict[str, Any]:
        """SUP-03: the agent is never called; the stage is recorded NO_GO by the Supervisor."""
        case_id, target = state["case_id"], Stage(str(state["target"]))
        results = state.get("results", {})
        first_open = next(s for s in state["stages"] if results.get(s, {}).get("decision") != "GO")
        message = f"{target.value} needs every earlier stage to be GO first; next is {first_open}"
        trace_id = state["trace_id"]
        blocked = self._error(
            case_id, target, trace_id, BlockerCode.SUP_UPSTREAM_NOT_GO, message
        ).model_copy(update={"decision": Decision.NO_GO, "question": message})
        run_id = self.store.stage_started(case_id, target.value, trace_id)
        self.store.stage_finished(run_id, blocked)  # visible in the stage tracker (UI-03)
        self.store.set_state(case_id, status="PAUSED", current_stage=first_open)
        results = {**results, target.value: blocked.model_dump(mode="json")}
        return {
            "results": results,
            "outcome": {"status": "PAUSED", "stage": target.value, "question": message},
        }

    def _routing(self, state: _State) -> dict[str, Any]:
        """Code node, not an agent (BR-12): validated amount → engine route → ledger."""
        case_id = state["case_id"]
        raw = self.ledger.get(case_id, AMOUNT_KEY)
        try:
            amount = Decimal(raw) if raw is not None else None
        except InvalidOperation:
            amount = None
        if amount is None:
            self.store.set_state(case_id, status="FAILED", current_stage=Stage.ROUTING.value)
            return {"outcome": {"status": "FAILED", "stage": "routing", "question": None}}
        route = route_amount(amount, self.boundary_rule)
        held = route == "HELD"
        reason = BlockerCode.SUP_ROUTE_HELD.value if held else None
        with span("route", trace_id=state["trace_id"], case_id=case_id, route=route):
            self.store.route(case_id, route, reason=reason)
        status = "HELD" if held else "AWAITING_APPROVAL"
        return {
            "outcome": {
                "status": status,
                "stage": None,
                "question": None,
                "route": route,
                "reason": reason,
            }
        }

    def _approval(self, state: _State) -> dict[str, Any]:
        """Human decision (OBJ-09): the graph waits here; only /decision resumes it."""
        answer = interrupt({"case_id": state["case_id"], "outcome": state["outcome"]})
        decision, back = answer["decision"], answer.get("return_stage")
        with span(
            "decision", trace_id=state["trace_id"], case_id=state["case_id"], decision=decision
        ):
            pass
        if decision == "return":
            stages = state["stages"]
            if back not in stages:  # decide() validates first; this guards a forged resume
                raise InvalidReturnStageError(f"unknown return stage {back!r}")
            keep = stages[: stages.index(back)]
            results = {k: v for k, v in state.get("results", {}).items() if k in keep}
            return {"results": results, "outcome": {"status": "RETURNED", "stage": back}}
        status = {"approve": "APPROVED", "reject": "REJECTED"}[decision]
        return {"outcome": {"status": status, "stage": None, "question": None}}

    # ---- one stage --------------------------------------------------------------------------
    def _invoke(
        self,
        case_id: str,
        stage: Stage,
        trace_id: str,
        findings: tuple[CriticFinding, ...] = (),
    ) -> AgentResult:
        agent_name = AgentName(stage.value)
        run_id = self.store.stage_started(case_id, stage.value, trace_id)
        with span("stage", case_id=case_id, stage=stage.value, trace_id=trace_id):
            # SUP-05 first (code is the authority on figures), then the Critic on the wording;
            # every regenerated result passes through the same gate again.
            result = self._gate(
                self._call_agent(case_id, stage, agent_name, trace_id, findings=findings)
            )
            result = self._criticise(case_id, stage, agent_name, trace_id, result)
        self.store.stage_finished(run_id, result)
        return result

    def invoke_extra(self, case_id: str, stage: Stage, agent: StageAgent, name: str) -> AgentResult:
        """A separate agent invocation outside the fixed plan (LW-12: the negotiation round).

        Same wrappers as a stage (case pinning, registry, budget, timeout, tracing, audit) and
        the same caps (SUP-07); it changes no workflow state and records no stage run, so the
        stage's own result and gate are untouched. Audited as ``EXTRA_INVOCATION``."""
        trace_id = uuid.uuid4().hex
        with span("stage", case_id=case_id, stage=f"{stage.value}.{name}", trace_id=trace_id):
            result = self._call_agent(case_id, stage, AgentName(stage.value), trace_id, agent)
            # No _criticise here: an extra invocation has side effects (the negotiation round
            # sends to the lender), so it is never re-run; it verifies its own message first.
            result = self._gate(result, recheck=False)
        self.store.audit(
            case_id,
            "EXTRA_INVOCATION",
            {
                "stage": stage.value,
                "name": name,
                "decision": result.decision.value,
                "steps": result.steps_used,
                "trace_id": trace_id,
            },
        )
        return result

    def _call_agent(
        self,
        case_id: str,
        stage: Stage,
        agent_name: AgentName,
        trace_id: str,
        override: StageAgent | None = None,
        *,
        findings: tuple[CriticFinding, ...] = (),
        template_only: bool = False,
    ) -> AgentResult:
        agent = override or self.agents[stage]
        llm = self.llm
        if llm is not None and getattr(llm, "circuit_state", "closed") == "open":
            llm = None
            self._fallback(case_id, stage, trace_id, "circuit_open")
        for _ in range(MAX_REPAIRS + 1):
            cancel = threading.Event()
            traced = _TracedLLM(llm, case_id, stage, cancel) if llm is not None else None
            ctx = StageContext(
                case_id=case_id,  # SUP-08: injected here, never read from model output
                tenant_id=self.tenant_id,
                stage=stage,
                trace_id=trace_id,
                ledger=_GuardedLedger(self.ledger, cancel, agent_name, case_id),
                tools=_AuditedTools(
                    self.tools(agent_name), self.store, agent_name, trace_id, cancel, case_id
                ),
                llm=traced,
                clock=self.clock,
                findings=findings,
                template_only=template_only,
                ablation=self.ablation,
            )
            try:
                with stage_budget(self.token_cap) as budget:
                    out: Any = self._run_with_timeout(agent, ctx, cancel)
            except ModelUnavailable:
                # scope #48: the template path every agent has for LLM_ENABLED=false.
                llm = None
                self._fallback(case_id, stage, trace_id, "model_unavailable")
                continue
            except (TimeoutError, LLMTimeout) as exc:
                _log.warning("timeout in %s on case %s (trace %s)", stage.value, case_id, trace_id)
                self.store.audit(
                    case_id,
                    "STAGE_TIMEOUT",
                    {"stage": stage.value, "trace_id": trace_id, "kind": type(exc).__name__},
                )
                return self._error(
                    case_id,
                    stage,
                    trace_id,
                    BlockerCode.SUP_TIMEOUT,
                    "model call timed out"
                    if isinstance(exc, LLMTimeout)
                    else f"stage ran past {self.stage_timeout:g} s",
                )
            except BudgetExceeded:
                return self._error(
                    case_id,
                    stage,
                    trace_id,
                    BlockerCode.SUP_BUDGET_EXCEEDED,
                    f"token budget of {self.token_cap} spent",
                )
            except LoopDetected:
                # S3: the tool name and arguments stay in the log, never in the stored blocker.
                _log.exception("loop in %s on case %s (trace %s)", stage.value, case_id, trace_id)
                return self._error(
                    case_id,
                    stage,
                    trace_id,
                    BlockerCode.SUP_BUDGET_EXCEEDED,
                    "loop: repeated identical tool call",
                )
            except Exception as exc:
                # NFR-07: the detail stays in the log; the stored, user-visible blocker is generic.
                _log.exception(
                    "agent %s failed on case %s (trace %s)", stage.value, case_id, trace_id
                )
                return self._error(
                    case_id,
                    stage,
                    trace_id,
                    BlockerCode.SUP_AGENT_ERROR,
                    f"agent error: {type(exc).__name__}",
                )
            try:
                raw = out.model_dump() if isinstance(out, AgentResult) else out
                result = AgentResult.model_validate(raw)
            except ValidationError:
                continue
            if result.case_id == case_id and result.stage is stage:
                return result.model_copy(
                    update={
                        "tokens_used": max(result.tokens_used, budget.used),
                        "prompt_versions": {
                            **(traced.versions if traced else {}),
                            **result.prompt_versions,
                        },
                    }
                )
        return self._error(
            case_id,
            stage,
            trace_id,
            BlockerCode.SUP_SCHEMA_INVALID,
            f"invalid result after {MAX_REPAIRS} repairs",
        )

    def _criticise(
        self,
        case_id: str,
        stage: Stage,
        agent_name: AgentName,
        trace_id: str,
        result: AgentResult,
        override: StageAgent | None = None,
    ) -> AgentResult:
        """VER-05, scope #21: the Critic checks the stage's narrative. Critical findings send the
        stage back with them (the agent drafts with ``regenerate``) at most MAX_REGENERATIONS
        times, then once with ``template_only``; a template that still fails is withheld and the
        stage is NO_GO. Each attempt is a new invocation with its own step cap (SUP-07)."""
        if self.critic is None or self.ablation == "A2" or stage is Stage.CRITIC:
            return result
        tries = 0
        while result.decision is not Decision.ERROR and result.narrative:
            found = [f for f in self.critic(result) if f.severity is FindingSeverity.CRITICAL]
            if not found:
                return result
            codes = sorted({f.code.value for f in found})
            self.store.audit(
                case_id,
                "CRITIC_BLOCKED",
                {"stage": stage.value, "attempt": tries + 1, "codes": codes, "trace_id": trace_id},
            )
            if self.llm is None or tries > MAX_REGENERATIONS:  # the template itself failed
                blockers = [Blocker(code=f.code, message=f.message) for f in found[:5]]
                return result.model_copy(
                    update={
                        "decision": Decision.NO_GO,
                        "narrative": WITHHELD,
                        "blockers": [*result.blockers, *blockers],
                    }
                )
            tries += 1
            last = tries > MAX_REGENERATIONS
            if last:
                self.store.audit(
                    case_id, "CRITIC_FALLBACK", {"stage": stage.value, "trace_id": trace_id}
                )
            result = self._gate(
                self._call_agent(
                    case_id,
                    stage,
                    agent_name,
                    trace_id,
                    override,
                    findings=tuple(found),
                    template_only=last,
                )
            )
        return result

    def _run_with_timeout(self, agent: StageAgent, ctx: StageContext, cancel: Any) -> Any:
        """scope #23: the agent runs in a worker thread (same trace and budget context). On
        timeout `cancel` is set, so the orphan's next model, tool or ledger call raises."""
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"stage-{ctx.stage.value}")
        future = pool.submit(contextvars.copy_context().run, agent, ctx)
        try:
            return future.result(timeout=self.stage_timeout)
        except TimeoutError:
            cancel.set()
            # ponytail: Python cannot kill a thread; orphans stop at their next port call.
            orphans = sum(t.name.startswith("stage-") for t in threading.enumerate())
            _log.warning("stage %s timed out; %d stage threads alive", ctx.stage.value, orphans)
            raise
        finally:
            pool.shutdown(wait=False)

    def _fallback(self, case_id: str, stage: Stage, trace_id: str, reason: str) -> None:
        self.store.audit(
            case_id, "LLM_FALLBACK", {"stage": stage.value, "reason": reason, "trace_id": trace_id}
        )

    def _gate(self, result: AgentResult, *, recheck: bool = True) -> AgentResult:
        """Caps (SUP-07), then the deterministic re-check on every GO (SUP-05, BR-11)."""
        if result.decision is Decision.ERROR:
            return result
        if result.steps_used > self.max_steps or result.tokens_used > self.token_cap:
            return result.model_copy(
                update={
                    "decision": Decision.ERROR,
                    "blockers": [
                        *result.blockers,
                        Blocker(
                            code=BlockerCode.SUP_BUDGET_EXCEEDED,
                            message=f"{result.steps_used} steps / {result.tokens_used} tokens "
                            f"exceeds {self.max_steps} / {self.token_cap}",
                        ),
                    ],
                }
            )
        if self.ablation == "A4" and self.llm is not None and recheck:  # model decides (BRD §12)
            return self._a4_gate(result)
        # A1: the engines are what the re-check runs, so with the model calculating there is none
        a1 = self.ablation == "A1" and result.stage in (Stage.WORKING_CAPITAL, Stage.LENDWISE)
        if not recheck or result.decision is not Decision.GO or a1 or self.ablation == "A4":
            return result
        try:
            failed = self.rechecks.get(result.stage, _evidence_and_gate_check)(result, self.ledger)
        except Exception as exc:  # fail closed with an audited stage result (SUP-05)
            _log.warning("recheck failed for %s: %s", result.stage.value, type(exc).__name__)
            return self._error(
                result.case_id,
                result.stage,
                result.trace_id,
                BlockerCode.SUP_AGENT_ERROR,
                "deterministic re-check failed",
            )
        if not failed:
            return result
        self.store.audit(
            result.case_id,
            "GATE_OVERRIDE",
            {"stage": result.stage.value, "codes": [b.code.value for b in failed]},
        )
        new = [b for b in failed if b not in result.blockers]
        return result.model_copy(
            update={"decision": Decision.NO_GO, "blockers": [*result.blockers, *new]}
        )

    def _a4_gate(self, result: AgentResult) -> AgentResult:
        """Ablation A4 only: the stage decision is read from the model's free-text verdict."""
        if self.llm is None:
            return result
        summary = "\n".join(
            [result.narrative or "", *[f"- {b.code.value}: {b.message}" for b in result.blockers]]
        )
        prompt = prompts()[A4_PROMPT].render(stage=result.stage.value, summary=redact(summary))
        try:
            verdict = self.llm.complete(prompt, name=A4_PROMPT).upper()
        except LLMError:
            return result
        found = re.search(r"\b(NEEDS_INPUT|NO[_-]GO|GO)\b", verdict)
        if found is None:
            return result
        word = found.group(1).replace("-", "_")
        return result.model_copy(update={"decision": Decision(word)})

    def _error(
        self, case_id: str, stage: Stage, trace_id: str, code: BlockerCode, message: str
    ) -> AgentResult:
        return AgentResult(
            agent=AgentName(stage.value),
            case_id=case_id,
            stage=stage,
            tenant_id=self.tenant_id,
            decision=Decision.ERROR,
            blockers=[Blocker(code=code, message=message)],
            trace_id=trace_id,
            agent_version=f"supervisor-{__version__}",
        )

    def _stop(self, result: AgentResult, status: str) -> dict[str, Any]:
        question = result.question or (result.blockers[0].message if result.blockers else None)
        self.store.set_state(result.case_id, status=status, current_stage=result.stage.value)
        return {"status": status, "stage": result.stage.value, "question": question}

    # ---- helpers ----------------------------------------------------------------------------
    def _config(self, case_id: str) -> Any:
        return {"configurable": {"thread_id": f"{self.tenant_id}:{case_id}"}}

    def _outcome(self, values: Mapping[str, Any]) -> RunOutcome:
        out = values.get("outcome") or {"status": "IN_PROGRESS"}
        stage = out.get("stage")
        return RunOutcome(
            status=out["status"],
            stage=Stage(stage) if stage else None,
            question=out.get("question"),
            reason=out.get("reason"),
            results={
                Stage(k): AgentResult.model_validate(v)
                for k, v in values.get("results", {}).items()
            },
        )
