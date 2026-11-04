# ADR 0018 — AgentResult contract, including agent_version

Status: Proposed · 2026-11-05 · Scope #25 · Not frozen

## Proposal
`packages/core` holds the shared contract from design-detail §2.1:

`Decision`, `EvidenceRef`, `Blocker` (code from the blocker catalogue), and `AgentResult` with `agent`, `case_id`, `stage`, `decision` (set by code only), `evidence`, `blockers`, `question`, `output_ref`, `narrative`, `prompt_versions`, `steps_used`, `tokens_used`, `trace_id`.

Two fields are on the model so a later freeze does not change the shape:

- `agent_version` (scope #25). The stage-retry route stays in Phase 9.
- `tenant_id`, default `default`. Putting `tenant_id` on case tables is scope #27 and stays in Phase 5. This ADR does not decide that.

`Plan` and `CriticFinding` are schema only. The planner graph is Phase 8. Critic regeneration is Phase 9d.

## What acceptance would mean
Status moves to Accepted only after the owner says so. There is no `FROZEN` marker in this change. Until then the contract may still gain a field, and G1 does not treat it as frozen.
