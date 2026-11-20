"""Per-stage token budget (SUP-07, NFR-03). The Supervisor opens one per stage; the model adapter
charges every call to it and refuses the next call once it is spent. A ContextVar, so it follows
the stage into its worker thread (copy_context) without being passed through the agent.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from credassure.core.errors import BudgetExceeded


@dataclass
class StageBudget:
    """``reserved`` counts calls in flight at their estimate, so parallel calls (9c per-offer
    extraction) see each other: a call starts only while used + reserved < cap. That is the
    serial rule (at most the last call crosses the cap) applied to parallel calls."""

    cap: int
    used: int = 0
    reserved: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def charge(self, tokens: int) -> None:
        """Thread-safe: parallel per-offer calls (9c) share one stage budget."""
        with self._lock:
            self.used += tokens

    def check(self) -> None:
        with self._lock:
            self._refuse_if_spent()

    def reserve(self, estimate: int) -> int:
        """Atomically refuse a spent budget, else hold ``estimate`` until ``settle``."""
        with self._lock:
            self._refuse_if_spent()
            self.reserved += estimate
            return estimate

    def settle(self, reservation: int, used: int) -> None:
        """Swap a reservation for the tokens actually used (0 when the call failed)."""
        with self._lock:
            self.reserved -= reservation
            self.used += used

    def _refuse_if_spent(self) -> None:
        if self.used + self.reserved >= self.cap:
            raise BudgetExceeded(
                f"{self.used} of {self.cap} tokens used, {self.reserved} reserved in flight"
            )


_budget: ContextVar[StageBudget | None] = ContextVar("stage_budget", default=None)


@contextmanager
def stage_budget(cap: int) -> Iterator[StageBudget]:
    """Every model call inside the block is charged here; once spent, the next call is refused."""
    budget = StageBudget(cap)
    token = _budget.set(budget)
    try:
        yield budget
    finally:
        _budget.reset(token)


def current_budget() -> StageBudget | None:
    return _budget.get()
