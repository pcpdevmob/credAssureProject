# ADR 0008 — Model resilience: timeouts, retries, circuit breaker, template fallback

Status: Accepted · 2026-11-07 · Scope #48, #23, #22 (limiter), #36; NFR-03/04/05/07

## Context
The course model endpoint is shared, rate-limited and sometimes slow or down. A small model call can hang,
a burst can hit 429s, and a dead endpoint must not stall a case or the demo (ARCHITECTURE Q5: gates,
calculations, routing and approval keep working with the model down). Phase 8 shipped a bare client whose
`circuit_state` was always "closed".

## Decision
1. **Timeouts.** 30 s per model-call attempt (`LLM_CALL_TIMEOUT_S`); 5 min per stage (`STAGE_TIMEOUT_S`).
   The agent runs in a worker thread with the stage's context copied in (trace id, token budget). On a
   stage timeout the Supervisor sets a cancel event; the orphan's next model, tool or ledger call raises
   `StageCancelledError`, so nothing it does afterwards is written. The stage ends `ERROR` with blocker
   `SUP_TIMEOUT`, audit `STAGE_TIMEOUT`, and the normal `stage_finished` + checkpoint save state. A model call
   that times out on every attempt (`LLMTimeout`) also ends as `SUP_TIMEOUT`.
2. **Retries.** At most 2, only on transient errors: connection, timeout, 429, 5xx. Backoff is full jitter in
   `[0, 0.5 · 2^n]` s. A 4xx is our bug and is raised at once. The SDK's own retries are off (`max_retries=0`)
   so the breaker sees one outcome per call.
3. **Circuit breaker.** 5 consecutive failed calls (after retries) open it for 60 s; while open,
   `complete` raises `ModelUnavailable` without touching the network. After 60 s one probe is let through
   (`half_open`): success closes, failure re-opens. `/v1/health/ready` reports the state.
4. **Template fallback.** Every agent already has a template path for `LLM_ENABLED=false`. The Supervisor
   passes `llm=None` to a stage when the circuit is open, and re-runs a stage once with `llm=None` when
   `ModelUnavailable` is raised inside it. Audit `LLM_FALLBACK {stage, reason}`. The planner falls back to the
   fixed plan.
5. **Shared rate limiter** (NFR-04). One in-process limiter (`LLM_RATE_PER_MINUTE`) for every agent call and
   the baseline harness; the Phase 11 harness goes through the gateway and so shares it.
6. **Token budget.** The Supervisor opens a per-stage budget (`TOKEN_CAP_PER_STAGE`); the client charges each
   call's `usage.total_tokens` and refuses the next call once spent (`BudgetExceeded` → `SUP_BUDGET_EXCEEDED`).
   The stage's `tokens_used` feeds the existing 70%/90% quota monitor.
7. **Cache.** SQLite, keyed by model + prompt name@version + messages + schema; temperature-0 calls only.
8. **Redaction** (`security.pii.redact`) on the prompt before the call and on the reply before return.
9. **Contract placement.** `LLMError` and its subclasses, the stage budget and the prompt registry live in
   `packages/core` (ADR 0006: agents reach the model only through ports and may not import `credassure.llm`).
   `packages/llm` keeps the adapter: client, breaker, limiter, cache, structured output.

## Consequences
- Python cannot kill a thread: an orphan keeps its CPU until its next guarded call. Agents must do their work
  through the ports (they already must, ADR 0006), so a pure-CPU loop is the only thing cancellation misses.
- `# ponytail:` the limiter and breaker are per process. If the baseline and the gateway hit the endpoint at the
  same time, move the limiter to a SQLite token bucket.
- Evidence: `packages/llm/tests/test_client.py`, `agents/supervisor/tests/test_resilience.py`; mutation results in
  PROGRESS.md (Phase 6 notes).
