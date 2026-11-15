# ADR 0018 — AgentResult contract, including agent_version

Status: Accepted · 2026-11-15 (proposed 2026-11-05) · Scope #25 · Frozen at G1 (provisional freeze, see PROGRESS.md)

## Decision
`packages/core` holds the shared contract from design-detail §2.1:

`Decision`, `EvidenceRef`, `Blocker` (code from the blocker catalogue), and `AgentResult` with `agent`, `case_id`, `stage`, `decision` (set by code only), `evidence`, `blockers`, `question`, `output_ref`, `narrative`, `prompt_versions`, `steps_used`, `tokens_used`, `trace_id`.

Two more fields are on the model, so the freeze does not have to change the shape later:

- `agent_version` (scope #25). The stage-retry route stays in Phase 9.
- `tenant_id`, default `default`. Putting `tenant_id` on case tables is scope #27 and stays in Phase 5. This ADR does not decide that.

`Plan` and `CriticFinding` are schema only. The planner graph is Phase 8. Critic regeneration is Phase 9d.

## Alternatives considered
| Alternative | Why rejected |
|---|---|
| Freeze the original design-detail §2.1 shape now and add `agent_version` and `tenant_id` later as breaking changes | All six owners build against this contract from Phase 9. A field added after the freeze needs a v2 contract, a migration of stored `stage_runs.result_json`, and a rerun of every agent's tests and of the affected eval categories. Both fields are already known to be needed (scope #25 retry and audit, scope #27 tenancy), so adding them now costs nothing. |
| A separate result contract for each agent | The Supervisor validates and repairs one schema (SUP-04) and re-runs the gate checks on it (SUP-05). The Critic, the ledger and the audit log read one shape. ADR 0005 keeps one shared contract in `packages/core`, and BRD §5.2 freezes "one shared result format". Six contracts would need six validators and six repair prompts, and they would drift apart between owners. Agent-specific output goes behind `output_ref`. |

## Consequences
- The contract is frozen. Changing it needs a new ADR and a major version of `packages/core`, and every affected agent's tests and eval categories are rerun and reported next to the old results.
- Optional fields with defaults may be added only through that same ADR process. They are not exempt.
