"""Hexagonal ports (scope #46, ADR 0006). The gateway injects the adapters (Phase 8).

`SupervisorPort` is how an agent's API router reaches the Supervisor. Agents never call each other.
`StageContext` is everything a stage agent may touch: case-scoped ports, never a raw database.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from credassure.core.enums import Stage
from credassure.core.results import AgentResult


class LLMPort(Protocol):
    def complete(self, prompt: str, *, name: str = "default") -> str: ...


class ToolPort(Protocol):
    def call(self, name: str, case_id: str, args: Mapping[str, Any] | None = None) -> Any: ...


class LedgerPort(Protocol):
    """Tenant-bound fact ledger. Only packages/ledger implements it (ADR 0005 rule 5)."""

    def get(self, case_id: str, key: str) -> str | None: ...

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
    ) -> int: ...


class RetrievalPort(Protocol):
    def search(self, query: str, case_id: str | None) -> list[str]: ...


class ClockPort(Protocol):
    def today(self) -> date: ...


@dataclass(frozen=True)
class StageContext:
    """One stage invocation. The Supervisor injects case_id; never from a model (SUP-08)."""

    case_id: str
    tenant_id: str
    stage: Stage
    trace_id: str
    ledger: LedgerPort
    tools: ToolPort
    llm: LLMPort | None  # None when LLM_ENABLED=false: narratives use templates
    clock: ClockPort


StageAgent = Callable[[StageContext], AgentResult]


class SupervisorStore(Protocol):
    """What the Supervisor writes: stage runs, case state, audit, routing (ledger adapter)."""

    def stage_started(self, case_id: str, stage: str, trace_id: str) -> int: ...

    def stage_finished(self, run_id: int, result: AgentResult) -> None: ...

    def set_state(self, case_id: str, *, status: str, current_stage: str | None) -> None: ...

    def audit(self, case_id: str, event_type: str, payload: dict[str, Any]) -> None: ...

    def route(self, case_id: str, route: str) -> None: ...


class SupervisorPort(Protocol):
    """Stage runs go through this interface, never straight into an agent (ADR 0005)."""

    def start_run(
        self, actor: Any, case_id: str, *, stage: str | None, idempotency_key: str | None
    ) -> dict[str, Any]: ...

    def latest_result(self, actor: Any, case_id: str, stage: str) -> AgentResult | None: ...

    def plan(self, actor: Any, case_id: str) -> dict[str, Any]: ...

    def run_stage(self, case_id: str, stage: str) -> AgentResult: ...


class UnavailableSupervisor:
    """Default dependency; the gateway overrides it with the real service."""

    def start_run(
        self, actor: Any, case_id: str, *, stage: str | None, idempotency_key: str | None
    ) -> dict[str, Any]:
        raise NotImplementedError("supervisor not wired")

    def latest_result(self, actor: Any, case_id: str, stage: str) -> AgentResult | None:
        raise NotImplementedError("supervisor not wired")

    def plan(self, actor: Any, case_id: str) -> dict[str, Any]:
        raise NotImplementedError("supervisor not wired")

    def run_stage(self, case_id: str, stage: str) -> AgentResult:
        # ponytail: kept until the Phase 8 agent routers move to start_run; then delete.
        raise NotImplementedError(f"stage {stage} is not implemented")
