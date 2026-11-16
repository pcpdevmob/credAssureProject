# ADR 0006 — Hexagonal agents: ports in core, adapters in packages

Status: Accepted · 2026-11-05 · Scope #46

## Decision
Agents depend on ports in `packages/core` (`LLMPort`, `ToolPort`, `LedgerPort`, `RetrievalPort`, `ClockPort`). The gateway injects the adapters. `SupervisorPort` is how a stage run reaches the Supervisor; agents do not call each other (ADR 0005).

The port protocols are in place. Adapters (LLM client, tool runner, ledger, retrieval, clock) arrive with the packages that own them, and the gateway wires them in Phase 8. This ADR does not add those adapters.

## Consequences
A test can pass a fake port. No agent imports the OpenAI SDK, SQLite, or Chroma. Import-linter keeps that boundary.

## Amendment 2026-11-16 (scope #33)
`LedgerPort.put_fact` takes an optional `provenance` mapping (`agent`, `stage`, `trace_id`). It is recorded in the FACT_WRITTEN
audit payload in the same transaction and feeds the lineage endpoint. Agents do not set it: the Supervisor's guarded ledger
injects its own and ignores any value an agent passes, so an agent cannot claim another agent's or stage's identity.
Additive and optional; existing callers and fakes are unaffected.
