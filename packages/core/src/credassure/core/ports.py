"""Hexagonal ports (scope #46). Adapters arrive with the packages that implement them.

`SupervisorPort` is how an agent stage run reaches the Supervisor. Agents never call each other.
"""

from datetime import date
from typing import Protocol

from credassure.core.results import AgentResult


class LLMPort(Protocol):
    def complete(self, prompt: str) -> str: ...


class ToolPort(Protocol):
    def call(self, name: str, case_id: str) -> str: ...


class LedgerPort(Protocol):
    def get(self, case_id: str, key: str) -> str | None: ...


class RetrievalPort(Protocol):
    def search(self, query: str, case_id: str | None) -> list[str]: ...


class ClockPort(Protocol):
    def today(self) -> date: ...


class SupervisorPort(Protocol):
    """Stage runs go through this interface, never straight into an agent (ADR 0005)."""

    def run_stage(self, case_id: str, stage: str) -> AgentResult: ...


class UnavailableSupervisor:
    """Placeholder until the Supervisor graph exists (Phase 8)."""

    def run_stage(self, case_id: str, stage: str) -> AgentResult:
        raise NotImplementedError(f"stage {stage} is not implemented")
