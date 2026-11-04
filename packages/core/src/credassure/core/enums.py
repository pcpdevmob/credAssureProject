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
