# ADR 0016 — Langfuse self-hosted in Docker Compose

Status: Accepted · 2026-11-05 · Approved by the project owner (Pritish) · Amends BRD v3.1 NFR-09 ("tracing goes to Langfuse Cloud")

## Context
BRD NFR-09 and design-detail §1 send traces to Langfuse Cloud; the original build kit said self-hosted. Mentor question Q8 asks
whether an external tracing service is acceptable. Traces carry redacted prompts and case facts (synthetic), so keeping
them on the team machine removes the external-data question and works offline during the demo.

## Decision
- Langfuse runs as the `langfuse` Compose profile in `deploy/compose/langfuse.yaml` (langfuse-web, langfuse-worker,
  Postgres, ClickHouse, Redis, MinIO, per the official compose file; images pinned by digest in Phase 12). Secrets come only
  from the gitignored `deploy/env/langfuse.env`. Python SDK major version 5 (`langfuse>=5,<6`). The gateway reads `LANGFUSE_HOST` (default `http://localhost:3000`),
  `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`.
- Pointing `LANGFUSE_HOST` at Langfuse Cloud remains possible with no code change; it is not the default.
- `TRACING_ENABLED=false` disables tracing entirely (test profile). The PII mask function (`security.pii.redact`) applies
  in every mode.

## Consequences
- More containers and memory on the demo machine; `make demo-reset` must not wipe the trace store unless asked.
- BRD NFR-09 should read "tracing goes to a Langfuse instance (self-hosted by default)" in the next BRD revision.
