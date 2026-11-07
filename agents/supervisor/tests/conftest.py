"""In-memory fakes for the Supervisor graph tests (Phase 8a, docs/build/phase8-api-spec.md).

No database, no network, no model: store, ledger, tools and clock are dict/list fakes, and the graph
uses LangGraph's InMemorySaver. The Supervisor is imported lazily inside ``build`` so a missing
implementation fails each test, not the whole directory.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from credassure.core.enums import AgentName, Decision, Stage
from credassure.core.ports import StageContext
from credassure.core.results import AgentResult, Blocker, EvidenceRef

CASE = "CA-2026-0001"
PLAN_STAGES = (Stage.ONBOARDING, Stage.WORKING_CAPITAL, Stage.LENDWISE, Stage.CRITIC)


class FakeStore:
    """Records every SupervisorStore call in order."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.audits: list[tuple[str, str, dict[str, Any]]] = []
        self.routes: list[tuple[str, str]] = []
        self.route_reasons: list[str | None] = []
        self.states: list[tuple[str, str, str | None]] = []
        self.started: list[tuple[str, str, str]] = []
        self.finished: list[tuple[int, AgentResult]] = []
        self._next_id = 0

    def stage_started(self, case_id: str, stage: str, trace_id: str) -> int:
        self._next_id += 1
        self.started.append((case_id, str(stage), trace_id))
        self.calls.append(("stage_started", case_id, str(stage)))
        return self._next_id

    def stage_finished(self, run_id: int, result: AgentResult) -> None:
        self.finished.append((run_id, result))
        self.calls.append(("stage_finished", run_id, str(result.stage)))

    def set_state(self, case_id: str, *, status: str, current_stage: str | None) -> None:
        self.states.append((case_id, status, None if current_stage is None else str(current_stage)))
        self.calls.append(("set_state", case_id, status))

    def audit(self, case_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.audits.append((case_id, event_type, payload))
        self.calls.append(("audit", case_id, event_type))

    def route(self, case_id: str, route: str, reason: str | None = None) -> None:
        self.routes.append((case_id, route))
        self.route_reasons.append(reason)
        self.calls.append(("route", case_id, route))

    def event_types(self) -> list[str]:
        return [event for _, event, _ in self.audits]


class FakeLedger:
    """Dict-backed LedgerPort: latest value per (case_id, key)."""

    def __init__(self, facts: Mapping[tuple[str, str], str] | None = None) -> None:
        self.facts: dict[tuple[str, str], str] = dict(facts or {})
        self.versions: dict[tuple[str, str], int] = {}

    def get(self, case_id: str, key: str) -> str | None:
        return self.facts.get((case_id, key))

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
    ) -> int:
        self.facts[(case_id, key)] = str(value)
        self.versions[(case_id, key)] = self.versions.get((case_id, key), 0) + 1
        return self.versions[(case_id, key)]


class FakeClock:
    def today(self) -> date:
        return date(2026, 11, 15)  # AS_OF_DATE, never date.today()


class FakeTools:
    def __init__(self, agent: AgentName) -> None:
        self.agent = agent
        self.calls: list[tuple[str, str, Mapping[str, Any] | None]] = []

    def call(self, name: str, case_id: str, args: Mapping[str, Any] | None = None) -> Any:
        self.calls.append((name, case_id, args))
        return None


class ToolsFactory:
    """``tools`` argument of the Supervisor: one FakeTools per requested agent."""

    def __init__(self) -> None:
        self.requested: list[AgentName] = []

    def __call__(self, agent: AgentName) -> FakeTools:
        self.requested.append(agent)
        return FakeTools(agent)


Output = Decision | AgentResult | BaseException | object


class ScriptedAgent:
    """A StageAgent. ``outputs`` is consumed one per call; the last entry repeats.

    A ``Decision`` becomes a real AgentResult for ``ctx.case_id``; an exception is raised;
    anything else (a string, a dict) is returned as-is to exercise the SUP-04 schema check.
    """

    def __init__(
        self,
        stage: Stage,
        outputs: Sequence[Output] = (Decision.GO,),
        *,
        blockers: Sequence[Blocker] = (),
        evidence: Sequence[EvidenceRef] = (),
        question: str | None = None,
        steps: int = 1,
        tokens: int = 10,
        on_call: Callable[[StageContext], None] | None = None,
    ) -> None:
        self.stage = stage
        self.outputs = list(outputs)
        self.blockers = list(blockers)
        self.evidence = list(evidence)
        self.question = question
        self.steps = steps
        self.tokens = tokens
        self.on_call = on_call
        self.contexts: list[StageContext] = []

    @property
    def calls(self) -> int:
        return len(self.contexts)

    def __call__(self, ctx: StageContext) -> Any:
        self.contexts.append(ctx)
        if self.on_call is not None:
            self.on_call(ctx)
        out = self.outputs[min(len(self.contexts), len(self.outputs)) - 1]
        if isinstance(out, BaseException):
            raise out
        if isinstance(out, Decision):
            return self.result(ctx, out)
        return out

    def result(self, ctx: StageContext, decision: Decision, **overrides: Any) -> AgentResult:
        fields: dict[str, Any] = dict(
            agent=AgentName(self.stage.value),
            case_id=ctx.case_id,
            stage=self.stage,
            tenant_id=ctx.tenant_id,
            decision=decision,
            evidence=self.evidence,
            blockers=self.blockers,
            question=self.question,
            steps_used=self.steps,
            tokens_used=self.tokens,
            trace_id=ctx.trace_id or "trace-test",
            agent_version="0.0.1-test",
        )
        fields.update(overrides)
        return AgentResult(**fields)


@dataclass
class Harness:
    sup: Any
    store: FakeStore
    ledger: FakeLedger
    tools: ToolsFactory
    agents: dict[Stage, ScriptedAgent] = field(default_factory=dict)


def passing_rechecks() -> dict[Stage, Callable[[AgentResult, Any], list[Blocker]]]:
    return {stage: (lambda _r, _l: []) for stage in PLAN_STAGES}


@pytest.fixture
def fake_ledger() -> type[FakeLedger]:
    """``fake_ledger({(case_id, key): value})`` → FakeLedger."""
    return FakeLedger


@pytest.fixture
def make_agent() -> Callable[..., ScriptedAgent]:
    """``make_agent(stage, decisions=[...], ...)`` → ScriptedAgent."""

    def _make(
        stage: Stage, decisions: Sequence[Output] = (Decision.GO,), **kw: Any
    ) -> ScriptedAgent:
        return ScriptedAgent(stage, decisions, **kw)

    return _make


@pytest.fixture
def build() -> Callable[..., Harness]:
    """Build a Supervisor over fakes. Unlisted stages get an all-GO agent.

    ``amount`` seeds ``wc.recommended_amount`` (rupees, Decimal text); None leaves it missing.
    Extra keyword arguments go straight to ``Supervisor(...)``.
    """

    def _build(
        *,
        agents: Mapping[Stage, ScriptedAgent] | None = None,
        amount: str | None = "14200000",
        llm: Any = None,
        **kwargs: Any,
    ) -> Harness:
        from langgraph.checkpoint.memory import InMemorySaver

        from credassure.agents.supervisor.graph import Supervisor

        all_agents = {stage: ScriptedAgent(stage) for stage in PLAN_STAGES}
        all_agents.update(agents or {})
        store, tools = FakeStore(), ToolsFactory()
        ledger = FakeLedger({(CASE, "wc.recommended_amount"): amount} if amount else None)
        sup = Supervisor(
            agents=dict(all_agents),
            store=store,
            ledger=ledger,
            tools=tools,
            llm=llm,
            clock=FakeClock(),
            checkpointer=InMemorySaver(),
            **kwargs,
        )
        return Harness(sup=sup, store=store, ledger=ledger, tools=tools, agents=all_agents)

    return _build
