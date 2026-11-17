# Architecture decision records

One file per decision, `NNNN-short-title.md`, status `Proposed | Accepted | Superseded by NNNN`.
Precedence (CLAUDE.md): BRD > ADRs > ARCHITECTURE.md > design-detail.md > DATA_SPEC > PHASE_PROMPTS.
An ADR that departs from the BRD records who approved it and the BRD clause it amends.

| # | Title | Status | Phase | Scope # |
|---|---|---|---|---|
| [0001](0001-stack.md) | Technology stack | Accepted | 0 | — |
| [0002](0002-threat-model.md) | Threat model (STRIDE) | Accepted (living) | 0 | 43 |
| [0003](0003-execution-guide-reconciliation.md) | Execution guide reconciliation | Accepted | — | — |
| [0004](0004-ui-deferred-api-first.md) | UI deferred; API-first | Accepted (updated by 0005) | — | — |
| [0005](0005-monorepo-structure.md) | Monorepo structure | Accepted | 0b | — |
| [0006](0006-hexagonal-agents.md) | Hexagonal agents: ports and adapters | Accepted (adapters in Phase 8) | 1, 8 | 46 |
| [0007](0007-async-stage-jobs.md) | Async stage jobs, SSE progress, Idempotency-Key, heartbeat lock | Accepted | 8 | 47 |
| [0008](0008-model-resilience.md) | Model resilience: timeouts, retries, circuit breaker, template fallback | Accepted | 6 | 48, 23, 22, 36 |
| [0009](0009-excluded-multi-agent-patterns.md) | Excluded multi-agent patterns (no agent-to-agent messaging, no inter-agent bus, no cross-case memory, no dynamic spawning) | Accepted | 1 | 26 |
| [0010](0010-rounding-policy.md) | Rounding policy (exact in engines, lakh round-up, display rounding) | Accepted | 1 | 8 |
| [0011](0011-repayment-calendar.md) | Repayment date to week mapping (calendar, holidays) | Accepted | 4 | 7 |
| [0012](0012-apr-convention.md) | APR annualisation convention | Accepted | 4 | — |
| [0013](0013-reranker.md) | Reranker | Accepted | 7 | — |
| [0014](0014-judge.md) | Automated judge | Accepted | 11 | 11 |
| [0015](0015-demo-mode.md) | Demo mode | Accepted | 12 | 17 |
| [0016](0016-langfuse-self-hosted.md) | Langfuse self-hosted in Compose (amends BRD NFR-09) | Accepted | 0 | 44 |
| [0017](0017-local-ollama.md) | Local default model: Ollama, Llama 3.1 8B | Accepted | 0, 6 | — |
| [0018](0018-agent-result-contract.md) | AgentResult contract, including agent_version | Accepted (frozen at G1) | 1 | 25 |
| [0019](0019-indian-corpus-and-kr04-distractors.md) | Indian-only real corpus; KR-04 distractors are Indian | Accepted | 2, 3, 7 | 14 |
| [0020](0020-data-acquisition-policy.md) | Data-acquisition policy (robots, rate, identification, terms, ingestion safety) | Accepted | 2, 7 | 14 |
| [0021](0021-calculation-conventions.md) | Calculation conventions shared by gold and engines | Accepted | 3, 4 | — |
| [0022](0022-ui-finbridge-nextjs.md) | Web UI is the finbridge Next.js app, API-only (amends 0005) | Accepted | UI | — |
| [0023](0023-ledger-is-record-for-offers.md) | Ledger facts + audit are the record for offers, evaluations and negotiation; offer tables dropped in Phase 10 | Accepted | 9c, 10 | 33 |
| [0024](0024-chromadb-accepted-risk.md) | chromadb 1.5.9 advisories accepted: embedded PersistentClient only, re-check at G3/G4 | Accepted | 7, 9c | 41 |
| [0025](0025-case-deletion-tombstone.md) | Case deletion: content removed, append-only record kept as a tombstone | Accepted | 10 | 39 |
| [0026](0026-kr04-superseded-data-correction.md) | KR-04 data correction: R-CG-C-274, R-SIDBI-P-008, R-CG-C-237 tagged superseded from their own text | Accepted | 10b | — |
