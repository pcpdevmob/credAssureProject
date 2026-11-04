"""Visible plan contract (scope #19 schema). The Supervisor graph is Phase 8."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from credassure.core.enums import Stage

FIXED_STAGES: tuple[Stage, ...] = (
    Stage.ONBOARDING,
    Stage.WORKING_CAPITAL,
    Stage.LENDWISE,
    Stage.CRITIC,
)


def _fixed_stages() -> list[Stage]:
    return list(FIXED_STAGES)


class Plan(BaseModel):
    """The stage list for one case. ``fixed`` cannot reorder the canonical plan."""

    schema_version: Literal["1.0"] = "1.0"
    case_id: str
    mode: Literal["fixed", "llm_proposes"] = "fixed"
    stages: list[Stage] = Field(default_factory=_fixed_stages)

    @model_validator(mode="after")
    def fixed_mode_keeps_the_canonical_order(self) -> "Plan":
        if self.mode == "fixed" and tuple(self.stages) != FIXED_STAGES:
            raise ValueError("fixed plan uses the canonical stage order")
        return self
