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
| [0027](0027-local-gates-replace-ci.md) | Local pre-push gates replace GitHub Actions CI (#28, #36, #51) | Accepted (amended by 0028) | 10b | 28, 36, 41, 51 |
| [0028](0028-ci-restored.md) | GitHub Actions CI restored alongside the pre-push gates; `make hr-db` | Accepted | S1 | 28, 36, 51 |
| [0029](0029-guardrail-pipeline.md) | Guardrail pipeline: one package, rails R1–R5, fail closed | Proposed | P0 → P3 | 55, 56 |
| [0030](0030-pii-policy-presidio.md) | PII policy: data classes, Presidio, money never masked | Proposed | P0 → P3 | 57, 58, 59 |
| [0031](0031-safety-v2-suite.md) | safety_v2: separately frozen 40-item safety suite | Proposed | P0 → P8 | 65, 66 |
| [0032](0032-copilot-v2-scope-and-v34-cuts.md) | Copilot v2 reduced scope, dual scoring, reranker on (scores the answerability gate only, amended 2026-11-24), plan v3.4 cuts (amends 0013) | Accepted | P0 → P4, P5 | 60–64 |
| [0033](0033-injection-design-patterns.md) | Prompt-injection design patterns as architecture | Proposed | P0 → P2 | 54 |
| [0034](0034-image-digest-pinning-deferred.md) | Image digest pinning: tooling now, pins from a networked machine | Accepted | P10 | 41 |
| [0035](0035-copilot-v3-product-assistant.md) | Copilot v3: Ask CredAssure as the product assistant on every page (amends 0032 §6) | Accepted | P13 | 2, 20 |
| [0036](0036-local-ollama-is-the-evaluated-path.md) | Local Ollama (qwen3:8b) is the evaluated path; course endpoint not used (amends 0017) | Accepted | P11 | 13 |
| [0037](0037-three-negotiation-rounds-and-reranking.md) | Three negotiation rounds by default, re-ranking after every counted concession (reinstates LW-15, amends 0032 §7) | Accepted | P11 | — |
| [0038](0038-accounts-mfa-and-segregation-in-the-gateway.md) | Accounts, MFA and segregation of duties in the gateway (bridge auth service retired 2026-11-20) | Accepted | P14 | 52 |
| [0039](0039-case-db-on-mysql.md) | case.db on MySQL for the hosted deployment; SQLite stays for hr.db, corpus.db (FTS5), checkpoints and eval (amends 0001) | Proposed | P15 | 22, 29, 38, 49 |
| [0040](0040-excel-workbook-import.md) | Excel workbook import for case data (same files, same upload checks); PDF stays out of scope (amends BRD Q-08, 0003) | Accepted | P9 | — |
| [0041](0041-lender-pdf-intake.md) | Lender PDFs: text layer, AI-suggested offer fields as quotes read by code, human review before saving (amends 0040) | Accepted | P9 | — |
| [0042](0042-retrieval-result-reported-as-measured.md) | Retrieval reported as measured on the frozen labels (22/40, shipped configuration chosen on the dev split); the miss is accepted, no relabelling (D1, H5) | Proposed | P4 | 60–63 |
