# Deployment

**Owner:** [Name 1] (TODO: name)
**Phases:** P6 (course switch, deferred), P10 (Phase 12)
**Status:** Local run + isolated e2e + demo-reset done; CI restored (ADR 0028); course endpoint deferred (under discussion)

## Open items
- Course endpoint switch (llm-probe, graded baseline, re-embed) — deferred until the course endpoint is agreed.
- Docker/Compose clean-machine run, replay mode, backup/restore, SBOM, tag v1.0.0 (P10).
- `make up` needs `deploy/env/langfuse.env` (HISTORY "Open questions").
