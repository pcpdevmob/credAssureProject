# ADR 0009 — Excluded multi-agent patterns

Status: Accepted · 2026-11-05 · Scope #26

## Decision
These patterns are out of the product:

- No agent-to-agent messaging. A hand-off goes through the Supervisor and the fact ledger.
- No inter-agent bus.
- No cross-case memory. A copilot turn and a tool call see one case.
- No dynamic spawning of agents.

The registry in `agents/registry.yaml` is a fixed allowlist. Code checks it. The model does not add tools or agents at runtime.

## Consequences
Import-linter already forbids one agent from importing another. The tool allowlist rejects a call that is not on the matrix. A later design that wants one of the excluded patterns needs a new ADR.
