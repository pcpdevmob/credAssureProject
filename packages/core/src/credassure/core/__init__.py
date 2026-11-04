"""Shared contract. Gates stay in code; this package only describes results (BR-11)."""

from credassure.core.ports import (
    ClockPort,
    LedgerPort,
    LLMPort,
    RetrievalPort,
    SupervisorPort,
    ToolPort,
    UnavailableSupervisor,
)
from credassure.core.results import AgentResult, Blocker, EvidenceRef

__all__ = [
    "AgentResult",
    "Blocker",
    "ClockPort",
    "EvidenceRef",
    "LLMPort",
    "LedgerPort",
    "RetrievalPort",
    "SupervisorPort",
    "ToolPort",
    "UnavailableSupervisor",
]
