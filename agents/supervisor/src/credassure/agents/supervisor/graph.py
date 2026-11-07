"""Supervisor workflow: a LangGraph state graph whose edges are decided by code (SUP-01..08).

    START → next → <first plan stage not GO> → next → … → routing → approval (interrupt) → END
    A paused, failed or single-stage run sets `outcome` and ends; resume re-enters at `next`, so
    only the blocked stage runs again (SUP-06). A return from the approver clears that stage on.

The model never decides order, gates or routes (BR-11). Agents are injected by the gateway and
never import each other (ADR 0005, ADR 0009); case_id is always the run's own (SUP-08).
"""

import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, NotRequired, TypedDict, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import ValidationError

from credassure.agents.supervisor import __version__
from credassure.core.blockers import BlockerCode, BlockerEffect, blocker_effect
from credassure.core.enums import AgentName, Decision, Stage
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
from credassure.core.results import AgentResult, Blocker
from credassure.engines.routing import route as route_amount
from credassure.observability.tracing import span
from credassure.tools.runner import LoopDetected

Recheck = Callable[[AgentResult, LedgerPort], list[Blocker]]
MAX_REPAIRS = 2  # SUP-04: an invalid result is re-requested at most twice
AMOUNT_KEY = "wc.recommended_amount"  # rupees, Decimal text (the threshold applies to it, Q-02)


@dataclass
class RunOutcome:
    # PAUSED | IN_PROGRESS | AWAITING_APPROVAL | HELD | FAILED | APPROVED | REJECTED | RETURNED
    status: str
    stage: Stage | None = None
    question: str | None = None
    results: dict[Stage, AgentResult] = field(default_factory=dict)


class _State(TypedDict):
    case_id: str
    stages: list[str]
    target: str | None
    outcome: dict[str, Any] | None
    results: NotRequired[dict[str, dict[str, Any]]]  # kept across runs by the checkpointer


def _evidence_and_gate_check(result: AgentResult, ledger: LedgerPort) -> list[Blocker]:
    """Skeleton re-check: no gate blocker on a GO, and every cited ledger fact exists."""
    failed = [b for b in result.blockers if blocker_effect(b.code) is BlockerEffect.GATE]
    for ref in result.evidence:
        if ref.kind == "ledger_fact" and ledger.get(result.case_id, ref.ref_id) is None:
            failed.append(
                Blocker(
                    code=BlockerCode.SUP_SCHEMA_INVALID,
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
    ) -> None:
        self.agents, self.store, self.ledger = agents, store, ledger
        self.tools, self.llm, self.clock = tools, llm, clock
        self.tenant_id = tenant_id
        self.rechecks = default_rechecks() if rechecks is None else dict(rechecks)
        self.max_steps, self.token_cap = max_steps, token_cap
        self.planner_mode, self.ablation = planner_mode, ablation
        self.boundary_rule: Literal["hold", "director", "vp"] = boundary_rule
        self.graph = self._build().compile(checkpointer=checkpointer)

    # ---- public API -------------------------------------------------------------------------
    def plan(self, case_id: str) -> Plan:
        """Visible plan (scope #19). The model may propose; code accepts only the fixed order."""
        plan, accepted = Plan(case_id=case_id), True
        if self.planner_mode == "llm_proposes":
            accepted = False
            if self.llm is not None:
                prompt = (
                    f"Propose the stage order for case {case_id} as a JSON list of: "
                    + ", ".join(s.value for s in FIXED_STAGES)
                )
                try:
                    proposed = json.loads(self.llm.complete(prompt, name="sup_plan"))
                    if isinstance(proposed, list) and tuple(proposed) == tuple(
                        s.value for s in FIXED_STAGES
                    ):
                        plan, accepted = Plan(case_id=case_id, mode="llm_proposes"), True
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
        with span(
            "plan",
            case_id=case_id,
            mode=plan.mode,
            stages=[s.value for s in plan.stages],
            accepted=accepted,
        ):
            return plan

    def run(self, case_id: str, *, stage: Stage | None = None) -> RunOutcome:
        config = self._config(case_id)
        snapshot = self.graph.get_state(config)
        if snapshot.next:  # waiting on the approver: nothing to run until a decision arrives
            return self._outcome(snapshot.values)
        plan = self.plan(case_id)
        state: _State = {
            "case_id": case_id,
            "stages": [s.value for s in plan.stages],
            "target": stage.value if stage else None,
            "outcome": None,
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
        """Resume the approval interrupt. The ledger already recorded the decision (APR-04)."""
        config = self._config(case_id)
        if not self.graph.get_state(config).next:
            raise ValueError(f"case {case_id} is not waiting for a decision")
        resume = {
            "decision": decision,
            "return_stage": return_stage.value if return_stage else None,
        }
        return self._outcome(self.graph.invoke(Command(resume=resume), config))

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
            result = self._invoke(state["case_id"], stage)
            results = {**state.get("results", {}), stage.value: result.model_dump(mode="json")}
            outcome: dict[str, Any] | None = None
            if result.decision is Decision.ERROR:
                outcome = self._stop(result, "FAILED")
            elif result.decision is not Decision.GO:
                outcome = self._stop(result, "PAUSED")
            elif state.get("target") is not None:
                outcome = {"status": "IN_PROGRESS", "stage": stage.value, "question": None}
            return {"results": results, "outcome": outcome}

        return node

    def _upstream_not_go(self, state: _State) -> dict[str, Any]:
        """SUP-03: the agent is never called; the stage is recorded NO_GO by the Supervisor."""
        case_id, target = state["case_id"], Stage(str(state["target"]))
        message = f"{target.value} needs every earlier stage to be GO first"
        blocked = self._error(
            case_id, target, uuid.uuid4().hex, BlockerCode.SUP_UPSTREAM_NOT_GO, message
        ).model_copy(update={"decision": Decision.NO_GO, "question": message})
        self.store.audit(case_id, "UPSTREAM_NOT_GO", {"stage": target.value})
        results = {**state.get("results", {}), target.value: blocked.model_dump(mode="json")}
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
        with span("route", case_id=case_id, route=route):
            self.store.route(case_id, route)
        status = "HELD" if route == "HELD" else "AWAITING_APPROVAL"
        return {"outcome": {"status": status, "stage": None, "question": None, "route": route}}

    def _approval(self, state: _State) -> dict[str, Any]:
        """Human decision (OBJ-09): the graph waits here; only /decision resumes it."""
        answer = interrupt({"case_id": state["case_id"], "outcome": state["outcome"]})
        decision, back = answer["decision"], answer.get("return_stage")
        if decision == "return" and back is not None:
            stages = state["stages"]
            keep = stages[: stages.index(back)] if back in stages else stages
            results = {k: v for k, v in state.get("results", {}).items() if k in keep}
            return {"results": results, "outcome": {"status": "RETURNED", "stage": back}}
        status = {"approve": "APPROVED", "reject": "REJECTED"}[decision]
        return {"outcome": {"status": status, "stage": None, "question": None}}

    # ---- one stage --------------------------------------------------------------------------
    def _invoke(self, case_id: str, stage: Stage) -> AgentResult:
        trace_id = uuid.uuid4().hex
        agent_name = AgentName(stage.value)
        run_id = self.store.stage_started(case_id, stage.value, trace_id)
        with span("stage", case_id=case_id, stage=stage.value, trace_id=trace_id):
            result = self._call_agent(case_id, stage, agent_name, trace_id)
            result = self._gate(result)
        self.store.stage_finished(run_id, result)
        return result

    def _call_agent(
        self, case_id: str, stage: Stage, agent_name: AgentName, trace_id: str
    ) -> AgentResult:
        agent = self.agents[stage]
        for _ in range(MAX_REPAIRS + 1):
            ctx = StageContext(
                case_id=case_id,  # SUP-08: injected here, never read from model output
                tenant_id=self.tenant_id,
                stage=stage,
                trace_id=trace_id,
                ledger=self.ledger,
                tools=self.tools(agent_name),
                llm=self.llm,
                clock=self.clock,
            )
            try:
                out: Any = agent(ctx)
            except LoopDetected as exc:
                return self._error(
                    case_id, stage, trace_id, BlockerCode.SUP_BUDGET_EXCEEDED, f"loop: {exc}"
                )
            except Exception as exc:
                return self._error(
                    case_id, stage, trace_id, BlockerCode.SUP_SCHEMA_INVALID, f"agent error: {exc}"
                )
            try:
                raw = out.model_dump() if isinstance(out, AgentResult) else out
                result = AgentResult.model_validate(raw)
            except ValidationError:
                continue
            if result.case_id == case_id and result.stage is stage:
                return result
        return self._error(
            case_id,
            stage,
            trace_id,
            BlockerCode.SUP_SCHEMA_INVALID,
            f"invalid result after {MAX_REPAIRS} repairs",
        )

    def _gate(self, result: AgentResult) -> AgentResult:
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
        if result.decision is not Decision.GO or self.ablation == "A4":  # A4: model decides gates
            return result
        failed = self.rechecks.get(result.stage, _evidence_and_gate_check)(result, self.ledger)
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
            results={
                Stage(k): AgentResult.model_validate(v)
                for k, v in values.get("results", {}).items()
            },
        )
