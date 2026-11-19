"""Diagnostics for the copilot's answer path: what the model drafted and what the Critic blocked.

Wraps the copilot's LLM and ToolPort for an evaluation script (never the product): the raw
``cp_answer`` draft, and for every ``verify_claims`` call the checked text with each finding's code,
message and the matched span. A reply that abstains only carries finding codes; this shows which
banned word or which cited figure caused it. Read-only: answers and scores are unchanged.
"""

from collections.abc import Mapping
from typing import Any


class TracedLLM:
    """Records the raw text of every ``cp_answer`` completion."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.drafts: list[str] = []

    def complete(
        self, prompt: str, *, name: str = "default", json_schema: Mapping[str, Any] | None = None
    ) -> str:
        out: str = self.inner.complete(prompt, name=name, json_schema=json_schema)
        if name == "cp_answer":
            self.drafts.append(out)
        return out

    def __getattr__(self, attr: str) -> Any:
        return getattr(self.inner, attr)


class TracedTools:
    """Records every ``verify_claims`` call: the text checked and the findings returned."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.checks: list[dict[str, Any]] = []

    def call(self, name: str, case_id: str, args: Mapping[str, Any] | None = None) -> Any:
        out = (
            self.inner.call(name, case_id, args)
            if args is not None
            else self.inner.call(name, case_id)
        )
        if name == "verify_claims":
            self.checks.append(
                {
                    "text": str((args or {}).get("text", ""))[:1200],
                    "findings": [
                        {"code": f.code.value, "message": f.message, "span": f.span} for f in out
                    ],
                }
            )
        return out


def snapshot(llm: TracedLLM, tools: TracedTools) -> dict[str, Any]:
    """The draft(s) and Critic checks of the last turn, then reset for the next item."""
    out = {"drafts": [d[:1500] for d in llm.drafts], "critic": list(tools.checks)}
    llm.drafts.clear()
    tools.checks.clear()
    return out
