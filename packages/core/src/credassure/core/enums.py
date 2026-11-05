"""Closed sets for the shared contract (design-detail §2.1)."""

from enum import StrEnum


class Decision(StrEnum):
    """Gate outcome. Set by code only; the model never assigns this (BR-11)."""

    GO = "GO"
    NO_GO = "NO_GO"
    NEEDS_INPUT = "NEEDS_INPUT"
    ERROR = "ERROR"


class AgentName(StrEnum):
    SUPERVISOR = "supervisor"
    ONBOARDING = "onboarding"
    WORKING_CAPITAL = "working_capital"
    LENDWISE = "lendwise"
    CRITIC = "critic"
    COPILOT = "copilot"


class Stage(StrEnum):
    ONBOARDING = "onboarding"
    WORKING_CAPITAL = "working_capital"
    LENDWISE = "lendwise"
    CRITIC = "critic"
    ROUTING = "routing"
    APPROVAL = "approval"


class AblationMode(StrEnum):
    """Ablations A1-A5 (BRD §12, scope #1). Phase 8/11 switch them; engines are the reference."""

    NONE = "none"
    A1_MODEL_CALCULATES = "A1"  # model computes cash table and APR instead of the engines
    A2_NO_LEDGER_CRITIC = "A2"  # fact ledger and Verification Critic off
    A3_DENSE_TOP5_ONLY = "A3"  # semantic top five only, no keyword search or reranking
    A4_MODEL_DECIDES_GATES = "A4"  # gates decided by the model in free text
    A5_NO_INJECTION_DEFENCE = "A5"  # documents not spotlighted, injection scan off
