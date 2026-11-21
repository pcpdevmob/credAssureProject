"""Primary → fallback model endpoint for the hosted deployment (deployment plan §5.3, ADR 0008).

Same LLMPort surface as one client. A call that ends in ModelUnavailable or LLMTimeout on the
primary (outage, timeout, wrong key/model/URL, or its circuit open) is sent once to the fallback.
A rejected request (LLMError) or a spent budget (BudgetExceeded) is raised as is: the fallback
would refuse the same request, and the budget is per stage, not per endpoint.

`circuit_state` is "open" only when both circuits are open, so the Supervisor keeps using the
model while the fallback serves and drops to templates only when neither endpoint answers.
"""

import logging
from collections.abc import Mapping
from typing import Any, Protocol

from credassure.llm.resilience import LLMTimeout, ModelUnavailable

_log = logging.getLogger("credassure.llm")
_RANK = {"closed": 0, "half_open": 1, "open": 2}


class _Client(Protocol):
    model: str

    @property
    def circuit_state(self) -> str: ...

    def complete(
        self, prompt: str, *, name: str = ..., json_schema: Mapping[str, Any] | None = ...
    ) -> str: ...


class FailoverLLM:
    def __init__(self, primary: _Client, fallback: _Client) -> None:
        self.primary, self.fallback = primary, fallback
        self.model = primary.model

    @property
    def circuit_state(self) -> str:
        return min((self.primary.circuit_state, self.fallback.circuit_state), key=_RANK.__getitem__)

    def complete(
        self, prompt: str, *, name: str = "default", json_schema: Mapping[str, Any] | None = None
    ) -> str:
        try:
            return self.primary.complete(prompt, name=name, json_schema=json_schema)
        except (ModelUnavailable, LLMTimeout) as exc:
            _log.warning(
                "llm failover",
                extra={"prompt": name, "reason": type(exc).__name__, "to": self.fallback.model},
            )
        return self.fallback.complete(prompt, name=name, json_schema=json_schema)
