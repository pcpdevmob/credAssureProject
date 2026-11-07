# ADR 0007 — Asynchronous stage jobs, SSE progress, Idempotency-Key

Status: Accepted · 2026-11-07 · Scope #47 (also #22, #23, SUP-06/07)

## Context
A full case run calls up to four agents, each with model calls of up to 30 s (ADR 0008). An HTTP request
that waits for the whole run times out in browsers and proxies, and a client retry would start a second
run. The Supervisor already allows only one run per case (`run_locks`, scope #22). Phase 5 left one
problem open: a lock was taken over after a fixed 5 minutes, even from a run that was still alive.

## Decision
1. **202 + job resource.** `POST /v1/cases/{id}/run` (and the per-stage wrappers) creates a `jobs` row
   (`queued`) and returns `202 Accepted` with `job_id`, `status_url` (`GET /v1/jobs/{id}`) and
   `events_url` (`GET /v1/jobs/{id}/events`). The run executes after the response, in-process
   (FastAPI background task). Job statuses: `queued → running → succeeded | failed | abandoned`;
   `outcome` holds the case status the run ended in (e.g. `AWAITING_APPROVAL`, `PAUSED`).
2. **Idempotency-Key.** An optional header. `(tenant_id, case_id, idempotency_key)` is unique in
   `jobs`; a repeated key returns the existing job and starts nothing new.
3. **SSE progress.** `events_url` is `text/event-stream`. The handler polls `stage_runs` and the job row
   (no in-memory bus, so it works after a restart or from another worker): one `stage` event per stage
   run and a final `end` event. No extra dependency (Starlette `StreamingResponse`).
4. **Heartbeat lock.** While a job runs, a heartbeat refreshes its `run_locks.acquired_at` every
   `HEARTBEAT` = 30 s (`session.heartbeat`). A lock is taken over only after three missed heartbeats
   (`STALE_LOCK` = 90 s). The job that lost its lock is marked `abandoned`; `heartbeat()` returns
   False to that run so it stops writing.
5. **Resume.** The LangGraph checkpoint (`SqliteSaver` on case.db, thread `tenant:case_id`) keeps stage
   results. A new job re-enters at the first stage that is not GO (SUP-06); a case waiting for its
   approver is not re-run (the approval `interrupt` stays pending until `/decision`).

## Consequences
- The client always polls or streams; tests rely on TestClient running background tasks before
  `post()` returns.
- ponytail: in-process jobs die with the process. The lock is freed 90 s later and the next run resumes
  from the checkpoint. A durable worker (ARCHITECTURE §11 debt) is the upgrade path; no code in the
  Supervisor changes.
- The 5-minute stage timeout (#23) is still enforced separately (Phase 6). The heartbeat is about lock
  liveness, not stage duration.
