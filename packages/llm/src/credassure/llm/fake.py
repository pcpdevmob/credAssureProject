"""FakeLLM: scripted replies keyed by prompt name, for tests and LLM-free CI (scope #15).

    llm = FakeLLM({"sup_plan": '["onboarding", ...]', "wc_explain": ["first", "second"]})

A list reply is consumed in order; its last item repeats. Unknown names get ``default``.
"""

from collections.abc import Mapping


class FakeLLM:
    circuit_state = "closed"

    def __init__(self, replies: Mapping[str, str | list[str]] | None = None, default: str = "ok"):
        self.replies = {
            k: list(v) if isinstance(v, list) else [v] for k, v in (replies or {}).items()
        }
        self.default = default
        self.calls: list[tuple[str, str]] = []

    def complete(self, prompt: str, *, name: str = "default") -> str:
        self.calls.append((name, prompt))
        queue = self.replies.get(name)
        if not queue:
            return self.default
        return queue.pop(0) if len(queue) > 1 else queue[0]
