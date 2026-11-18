# Deployment

**Owner:** [Name 1] (TODO: name)
**Phases:** P6 (course switch, deferred), P10 (Phase 12)
**Status:** Local run, isolated e2e, demo-reset, replay mode, backup/restore, release bundle + SBOM, runbook done (P10); clean-machine run passed; course endpoint deferred

## Open items
- Course endpoint switch (llm-probe, graded baseline, re-embed) — deferred until the course endpoint is agreed.
- Pin image digests from a networked machine (`make pin-images`, H17, ADR 0034).
- Docker Compose run on the Mac (`make up`); record replies for `REPLAY_MODE` during the rehearsal.
- `make up` needs `deploy/env/langfuse.env` (HISTORY "Open questions").
