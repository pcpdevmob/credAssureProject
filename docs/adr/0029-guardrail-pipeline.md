# ADR 0029 — Guardrail pipeline: one package, five rails, fail closed

Status: Proposed · Date: 2026-11-18 · Plan v3.4 §3 · Scope #55, #56 · Builds on ADR 0006 (hexagonal agents), ADR 0008 (model resilience)

## Context
Phase 6 already built most guardrails: PII masking with the Aadhaar Verhoeff check, the injection scanner, spotlighting, structured-output repair, the Critic, refusal rules, step and token caps, the circuit breaker, the ToolRunner allowlist and loop detection, and the L3/L4 excerpt cap on citations. They live in `packages/llm`, `packages/core`, `packages/security`, the gateway and the adapters, and their decisions are not logged as one event type, so the report cannot show "what the guardrails did" for a case.

## Decision
1. **Consolidate, don't rewrite.** Create `packages/guardrails`; move the existing controls behind the **same interfaces** with re-exports so callers do not change. The move lands as its own commit with `make check` green and the test count not lower.
2. **Five rails at the existing seams.**

| Rail | Seam | Controls |
|---|---|---|
| R1 input | gateway upload and chat routers | authz, size/rate limits, schema, PII detect → placeholder/refuse, injection score, scope (SUP-02) |
| R2 retrieval | `packages/retrieval` search and the citation endpoint | server-side tenant/case filter, ADR 0019 filters, datamarking, instruction-span flags, excerpt cap |
| R3 tool | ToolRunner | per-agent allowlist, JSON-schema args, server-injected `case_id`, read-only tools, budgets, loop detection |
| R4 output | structured output + Critic | schema repair ×2, numbers vs ledger, citation spans, banned content, PII re-scan, sanitisation, AI label |
| R5 telemetry | Langfuse exporter | mask before export, `gen_ai.*` attributes, hashed user ids |

3. **Layering.** `core` ← `guardrails` ← `llm`, `adapters`, gateway. Agents still never import `credassure.llm` (ADR 0006). Import-linter gains: `guardrails` imports only `core` and `security`; no agent imports `guardrails` internals except its public API.
4. **Policy file.** `config/guardrails.yaml` (thresholds, phrase lists, rule ids) is versioned and hashed like the prompt registry; `make eval-fast` fails on a change without a version bump.
5. **Evidence without flooding the audit chain.** `guardrail_event {rail, rule_id, action, case_id, trace_id}`: blocks, redactions and flags go to the audit log; passes go to traces only.
6. **Fail closed.** PII detector error → do not store; scorer error → treat as suspicious; output-rail error → fixed template.

## Consequences
- The report can show per-case guardrail activity and a safety panel (P9) reads the events.
- No new model calls; the token quota is unaffected.
- A guard model is not part of the pipeline (A7 stays a stretch ablation, ADR 0032).
