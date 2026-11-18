# ADR 0033 — Prompt-injection design patterns as architecture

Status: Proposed · Date: 2026-11-18 · Plan v3.4 §3.2 · Scope #54 · Relates to BR-15, ADR 0009

## Context
"Assume the model will be fooled": once an agent has read untrusted text, that text must not be able to trigger a consequential action. The 2025 design-patterns paper (Beurer-Kellner et al., arXiv 2506.08837) names six patterns. CredAssure already uses four, but nothing states it or tests it as a pattern.

## Decision
CredAssure's defence against injection is architectural; filters are a second layer. Each pattern gets a named test:

| Pattern | Where | Test |
|---|---|---|
| Plan-then-execute | Stage order fixed in code before any document is read (SUP-01) | A KFS saying "skip to approval" (and a Hinglish variant) leaves the plan and stage order unchanged and is flagged |
| LLM map-reduce | LendWise audits one offer per call; code merges and ranks | One poisoned KFS changes no field of another offer's audit, APR or ranking |
| Context-minimisation | Narratives see ledger slots only | Narrative calls contain no raw document text and no user chat |
| Action-selector | Copilot routing, refusal and abstention are code; the model picks from a fixed tool list | Router output is an enum; a passage cannot add a tool |

Dual-LLM and code-then-execute are not used (no privileged/quarantined model split; no generated code is executed).

## Consequences
- The tests run in `make check` (P2) and are cited in the threat model (P10).
- A new agent or tool must state which pattern contains its untrusted input.
