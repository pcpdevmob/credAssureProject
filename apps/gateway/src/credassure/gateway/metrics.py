"""In-process metrics in Prometheus text format (ARCHITECTURE §8.8: RED per endpoint, model calls).

Counters live in memory for this gateway process; a restart resets them (a scraper handles that).
Labels are bounded: HTTP routes use the route template (`/v1/cases/{case_id}`), never the raw
path, and model-call outcomes are a fixed set. No label ever holds case data or user input.
"""

import threading
import time
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from credassure.core.errors import BudgetExceeded, LLMError, LLMTimeout, ModelUnavailable

BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
CLIENT_ERROR_KINDS = ("error", "unhandledrejection", "render")


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests: dict[tuple[str, str, str], int] = defaultdict(int)
        self.duration: dict[tuple[str, str], list[float]] = {}
        self.llm_calls: dict[tuple[str, str], int] = defaultdict(int)
        self.llm_seconds: dict[str, float] = defaultdict(float)
        self.client_errors: dict[str, int] = defaultdict(int)
        self.unhandled = 0

    def http(self, method: str, route: str, status: int, seconds: float) -> None:
        with self._lock:
            self.requests[(method, route, str(status))] += 1
            counts = self.duration.setdefault((method, route), [0.0] * (len(BUCKETS) + 2))
            for i, edge in enumerate(BUCKETS):
                if seconds <= edge:
                    counts[i] += 1
            counts[-2] += 1  # +Inf / count
            counts[-1] += seconds  # sum

    def llm(self, prompt: str, outcome: str, seconds: float) -> None:
        with self._lock:
            self.llm_calls[(prompt, outcome)] += 1
            self.llm_seconds[prompt] += seconds

    def client_error(self, kind: str) -> None:
        with self._lock:
            self.client_errors[kind if kind in CLIENT_ERROR_KINDS else "error"] += 1

    def unhandled_error(self) -> None:
        with self._lock:
            self.unhandled += 1

    def render(self) -> str:
        out: list[str] = []
        with self._lock:
            out += [
                "# HELP credassure_http_requests_total HTTP requests by route template and status.",
                "# TYPE credassure_http_requests_total counter",
            ]
            for (m, r, s), n in sorted(self.requests.items()):
                labels = _labels(method=m, route=r, status=s)
                out.append(f"credassure_http_requests_total{labels} {n}")
            out += [
                "# HELP credassure_http_request_duration_seconds Request latency.",
                "# TYPE credassure_http_request_duration_seconds histogram",
            ]
            for (m, r), counts in sorted(self.duration.items()):
                for i, edge in enumerate(BUCKETS):
                    labels = _labels(method=m, route=r, le=str(edge))
                    out.append(
                        f"credassure_http_request_duration_seconds_bucket{labels} {int(counts[i])}"
                    )
                inf = _labels(method=m, route=r, le="+Inf")
                base = _labels(method=m, route=r)
                out.append(
                    f"credassure_http_request_duration_seconds_bucket{inf} {int(counts[-2])}"
                )
                out.append(
                    f"credassure_http_request_duration_seconds_count{base} {int(counts[-2])}"
                )
                out.append(f"credassure_http_request_duration_seconds_sum{base} {counts[-1]:.6f}")
            out += [
                "# HELP credassure_llm_calls_total Model calls by prompt and outcome.",
                "# TYPE credassure_llm_calls_total counter",
            ]
            for (p, o), n in sorted(self.llm_calls.items()):
                out.append(f"credassure_llm_calls_total{_labels(prompt=p, outcome=o)} {n}")
            out += [
                "# HELP credassure_llm_call_seconds_total Time spent in model calls by prompt.",
                "# TYPE credassure_llm_call_seconds_total counter",
            ]
            for p, secs in sorted(self.llm_seconds.items()):
                out.append(f"credassure_llm_call_seconds_total{_labels(prompt=p)} {secs:.6f}")
            out += [
                "# HELP credassure_client_errors_total Browser errors reported by the web app.",
                "# TYPE credassure_client_errors_total counter",
            ]
            for k, n in sorted(self.client_errors.items()):
                out.append(f"credassure_client_errors_total{_labels(kind=k)} {n}")
            out += [
                "# HELP credassure_unhandled_errors_total Server errors answered with a 500.",
                "# TYPE credassure_unhandled_errors_total counter",
                f"credassure_unhandled_errors_total {self.unhandled}",
            ]
        return "\n".join(out) + "\n"


def _labels(**kv: str) -> str:
    def esc(v: str) -> str:
        return v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    return "{" + ",".join(f'{k}="{esc(v)}"' for k, v in kv.items()) + "}"


def _outcome(exc: BaseException) -> str:
    if isinstance(exc, LLMTimeout):
        return "timeout"
    if isinstance(exc, BudgetExceeded):
        return "budget"
    if isinstance(exc, ModelUnavailable):
        return "unavailable"
    if isinstance(exc, LLMError):
        return "error"
    return "exception"


class MeteredLLM:
    """LLMPort wrapper that counts every call by prompt and outcome. Everything else (circuit
    state, replay flag, test helpers) is delegated, so health checks and fakes are unchanged."""

    def __init__(self, inner: Any, metrics: Metrics) -> None:
        self._inner, self._metrics = inner, metrics

    def complete(
        self, prompt: str, *, name: str = "default", json_schema: Mapping[str, Any] | None = None
    ) -> str:
        started = time.monotonic()
        try:
            reply = self._inner.complete(prompt, name=name, json_schema=json_schema)
        except BaseException as exc:
            self._metrics.llm(name, _outcome(exc), time.monotonic() - started)
            raise
        self._metrics.llm(name, "ok", time.monotonic() - started)
        return str(reply)

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._inner, attr)
