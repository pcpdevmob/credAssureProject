"""ToolPort adapter: allowlist check, retries and loop detection (scope #4, #24, SUP-07).

One runner serves one agent invocation. The Supervisor builds a fresh runner per stage call,
so loop memory never spans invocations or cases.
"""

import json
from collections.abc import Callable, Mapping
from typing import Any

from credassure.core.enums import AgentName

from .registry import authorize

MAX_RETRIES = 2  # SUP-07: a failing tool is retried at most twice


class LoopDetected(RuntimeError):  # noqa: N818 - name in the Phase 8 spec
    """The same tool was called again with the same arguments in one invocation (scope #4)."""


class ToolError(RuntimeError):
    """A transient tool failure that may be retried."""


class ToolRunner:
    def __init__(self, agent: AgentName | str, handlers: Mapping[str, Callable[..., Any]]) -> None:
        self.agent, self.handlers = agent, handlers
        self._seen: set[str] = set()

    def call(self, name: str, case_id: str, args: Mapping[str, Any] | None = None) -> Any:
        authorize(self.agent, name, case_id=case_id)
        args = dict(args or {})
        key = json.dumps([name, case_id, args], sort_keys=True, default=str)
        if key in self._seen:
            raise LoopDetected(f"{name} called twice with the same arguments")
        self._seen.add(key)
        for attempt in range(MAX_RETRIES + 1):
            try:
                return self.handlers[name](case_id=case_id, **args)
            except ToolError:
                if attempt == MAX_RETRIES:
                    raise
        raise AssertionError("unreachable")  # pragma: no cover
