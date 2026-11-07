"""Circuit breaker and shared rate limiter (ADR 0008; scope #22, #48; NFR-04). Thread-safe,
with injectable clocks so tests never sleep. The error types and the stage budget are part of
the port contract, so they live in packages/core and are re-exported here.
"""

import threading
import time
from collections.abc import Callable
from typing import Literal

from credassure.core.budget import StageBudget, current_budget, stage_budget
from credassure.core.errors import BudgetExceeded, LLMError, LLMTimeout, ModelUnavailable

__all__ = [
    "BudgetExceeded",
    "CircuitBreaker",
    "LLMError",
    "LLMTimeout",
    "ModelUnavailable",
    "RateLimiter",
    "StageBudget",
    "configure_shared_limiter",
    "current_budget",
    "shared_limiter",
    "stage_budget",
]

Clock = Callable[[], float]


class CircuitBreaker:
    """`failures` consecutive failed calls open the circuit for `open_s` seconds. After that one
    probe is let through (half_open): success closes it, failure re-opens it."""

    def __init__(self, failures: int = 5, open_s: float = 60.0, clock: Clock = time.monotonic):
        self.failures, self.open_s, self._clock = failures, open_s, clock
        self._count = 0
        self._opened_at: float | None = None
        self._probing = False
        self._lock = threading.Lock()

    @property
    def state(self) -> Literal["closed", "open", "half_open"]:
        if self._opened_at is None:
            return "closed"
        return "half_open" if self._clock() - self._opened_at >= self.open_s else "open"

    def before_call(self) -> None:
        """Raise while open; in half_open let exactly one caller through as the probe."""
        with self._lock:
            state = self.state
            if state == "open" or (state == "half_open" and self._probing):
                raise ModelUnavailable("model circuit is open")
            self._probing = state == "half_open"

    def success(self) -> None:
        with self._lock:
            self._count, self._opened_at, self._probing = 0, None, False

    def failure(self) -> None:
        with self._lock:
            half_open = self.state == "half_open"
            self._probing = False
            self._count += 1
            if half_open or self._count >= self.failures:
                self._opened_at = self._clock()


class RateLimiter:
    """Spaces calls `60 / per_minute` seconds apart across all threads (NFR-04)."""

    def __init__(
        self,
        per_minute: float,
        clock: Clock = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.interval = 60.0 / per_minute
        self._clock, self._sleep = clock, sleep
        self._next = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = self._clock()
            wait = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.interval
        if wait:
            self._sleep(wait)


# ponytail: one limiter per process, i.e. per team while the gateway is the only caller.
# A SQLite token bucket is the upgrade if the baseline and the gateway hit the endpoint together.
_shared = RateLimiter(60)


def shared_limiter() -> RateLimiter:
    """The limiter every agent call and the eval/baseline harness go through (scope #22)."""
    return _shared


def configure_shared_limiter(per_minute: float) -> RateLimiter:
    global _shared
    _shared = RateLimiter(per_minute)
    return _shared
