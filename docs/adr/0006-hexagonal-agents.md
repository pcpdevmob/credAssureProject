# ADR 0006 — Hexagonal agents: ports in core, adapters in packages

Status: Accepted · 2026-11-05 · Scope #46

## Decision
Agents depend on ports in `packages/core` (`LLMPort`, `ToolPort`, `LedgerPort`, `RetrievalPort`, `ClockPort`). The gateway injects the adapters. `SupervisorPort` is how a stage run reaches the Supervisor; agents do not call each other (ADR 0005).

The port protocols are in place. Adapters (LLM client, tool runner, ledger, retrieval, clock) arrive with the packages that own them, and the gateway wires them in Phase 8. This ADR does not add those adapters.

## Consequences
A test can pass a fake port. No agent imports the OpenAI SDK, SQLite, or Chroma. Import-linter keeps that boundary.
