# CredAssure — Complete build scope (53 items + 16 plan v3.4 items)

Every item below is part of the baseline build, built in the phase named in its row and verified by the evaluation listed in prompts/.
Nothing here is optional. If time runs short, the only permitted cut order is #35, #41, #38, #37, and each cut needs an ADR.

Source: Capstone Build Pack, Part 4. Each row names the phase where it is built.
Block → phase map: A=0, B=1, C=2, D=3, E=8 then 5, F=4, G=6, H=7, I1..I5=9a..9e, I6=8/9 Supervisor, J=10, K=11, L=12.

## A. Requirement and track items
| # | Item | Build | Phase |
|---|---|---|---|
| 1 | Ablation switch paths | eval/ablation_modes.py + hooks behind ABLATION=A1..A5 (A1 model calculates, A4 model decides gates) | 11 (built in 4/8 hooks) |
| 2 | Copilot conversation state | agents/copilot/memory.py: last N redacted turns per case, never cross-case | 9e |
| 3 | Model card / responsible AI | docs/security/model-card.md + docs/SYSTEM_CARD.md (P10) | 12 |
| 4 | Loop detection | repeated identical tool call (name+args hash) → ERROR | 8 |
| 5 | Cost per query | tokens × configurable notional price, per stage and item | 11 |
| 6 | Proposal versioning / staleness | reports/versioning.py stores ledger fact versions | 10 |
| 7 | Repayment date → week mapping | ADR + engines/calendar.py | 4 |
| 8 | Rounding policy | ADR: exact inside engines, round for display, lakh round-up | 1 |
| 9 | Blocker catalogue | domain/blockers.py | 1 |
| 10 | Required report sections config | reports/sections.yaml | 10 |
| 11 | Judge calibration | eval/judge label export, agreement + Cohen's kappa | 11 |
| 12 | Failure-class tagging | rule-based first guess + human confirm | 11 |
| 13 | Eval reproducibility record | model, prompt versions, engine version, corpus hash, seed per result | 3 |
| 14 | Corpus legal-basis audit | data/corpus/audit.py (fails on missing basis or committed L3/L4 file) | 2 |
| 15 | Full-case CI test with FakeLLM | tests/e2e/test_demo_case.py | 8 |
| 16 | Endpoint health + quota monitor | /health checks model; 70%/90% banners | 8 |
| 17 | Demo resilience | make demo-reset, replay recorder, screen recording | 12 |
| 18 | Contribution evidence | CONTRIBUTIONS.md per member | ongoing |

## B. Multi-agent system items
| # | Item | Build | Phase |
|---|---|---|---|
| 19 | Visible planner | agents/supervisor/plan.py: Plan per case logged as a span; PLANNER_MODE=fixed\|llm_proposes (code validates); report plan-acceptance rate | 8, 9 |
| 20 | Model-directed tool selection in core | copilot chooses among search_regulations, search_policies, get_case_facts, explain_blocker; code validates | 9e |
| 21 | Critic → agent feedback contract | domain/findings.py CriticFinding → regenerate v1 prompt per agent | 9d |
| 22 | Concurrency | SQLite WAL, busy_timeout 5000, one active run per case, harness concurrency ≤ rate limit, LendWise per-offer calls in parallel under shared limiter | 5, 6 |
| 23 | Timeouts and cancellation | 30 s per model call, 5 min per stage, state saved, TIMEOUT blocker | 6 |
| 24 | Agent registry + data-access matrix | agents/registry.yaml enforced in tool layer | 1 |
| 25 | Agent versioning + stage retry | agent_version in AgentResult (ADR — contract change); POST /v1/agents/supervisor/cases/{id}/stages/{stage}/retry (evaluator, FAILED case only) | 1, 9 |
| 26 | ADR on excluded patterns | no agent-to-agent messaging, no inter-agent bus, no cross-case memory, no dynamic spawning | 1 |

## C. Enterprise practices at capstone scale
| # | Practice | Capstone version | Phase |
|---|---|---|---|
| 27 | Multi-tenancy readiness | tenant_id on case tables, default tenant, all queries scoped | 5 |
| 28 | API versioning | /v1 prefix; CI fails on breaking openapi.json diff | 8 |
| 29 | Migrations | Alembic up/down tested; seeds separate | 5 |
| 30 | Config + feature flags | settings validated at startup; flag table in README | 0 |
| 31 | Structured logging | JSON with request_id, case_id, trace_id, agent, stage; PII redacted | 0 |
| 32 | Error catalogue | stable codes for API errors and blockers | 1 |
| 33 | Explainability endpoint | GET /v1/cases/{id}/facts/{key}/lineage | 10 |
| 34 | Graceful degradation matrix | documented + fault-injection flags | 11 |
| 35 | Performance smoke | 10 concurrent cases, p95 per stage | 11 |
| 36 | Prompt/model change control | prompts/** change → fast eval subset in CI; version bump required | 6 |
| 37 | Release management | semver tags, CHANGELOG, bundle = image digest + data hashes + eval report | 12 |
| 38 | Backup / restore | make backup / make restore (SQLite online backup), tested once | 12 |
| 39 | Data deletion workflow | DELETE /v1/cases/{id}, audit tombstone kept | 10 |
| 40 | Chat notice and consent | first-use notice, acknowledgement stored | 10 |
| 41 | Supply-chain evidence | SBOM in CI, images pinned by digest | 12 |
| 42 | Ownership and review | CODEOWNERS per agent dir; PR template with requirement IDs + eval impact | 0 |
| 43 | Architecture records | C4 (Mermaid), ADR index, risk register mapped to OWASP Top 10 for LLM apps | 0, weekly |
| 44 | Environment profiles | dev / test (FakeLLM) / demo (replay) Compose profiles | 0 |
| 45 | Runbook | RUNBOOK.md: endpoint down, quota exhausted, DB locked, corpus missing, demo reset | 12 |

## D. Architecture (ARCHITECTURE v2)
| # | Item | Fix | Phase |
|---|---|---|---|
| 46 | Hexagonal agents | Ports (LLMPort, ToolPort, LedgerPort, RetrievalPort, ClockPort) in packages/core; adapters injected by gateway; ADR 0006 | 1, 8 |
| 47 | Async stage jobs | POST run → 202 + job resource; SSE progress; Idempotency-Key; ADR 0007 | 8 |
| 48 | Model resilience | Circuit breaker (5 failures → open 60 s → templates), retries only on transient errors, jitter; ADR 0008 | 6 |
| 49 | Transactional audit | Ledger write and audit event in one transaction; optimistic concurrency (row_version) on cases/approvals | 5 |
| 50 | Health probes | /health/live and /health/ready (DB, Chroma, model circuit) | 8 |
| 51 | API fuzzing | Schemathesis against openapi.json in CI | 10 |
| 52 | Web security headers | CSP, CORS allowlist, no tokens in localStorage | UI U1 |
| 53 | Architecture conformance check | /eval E18 at G3 and G4 | 10, 12 |

## F. Plan v3.4 additions (2026-11-18; `docs/plan/CredAssure_RAI_Security_Copilot_Plan_v3.4.md`)
| # | Item | Build | Phase |
|---|---|---|---|
| 54 | Injection design-pattern tests | plan-then-execute, map-reduce isolation, context-minimisation tests (plan §3.2) | P2 |
| 55 | Guardrails package | `packages/guardrails` (R1–R5) consolidating Phase 6 controls behind the same interfaces; import-linter contracts | P3 |
| 56 | Guardrail events + policy | `guardrail_event` (blocks, redactions, flags → audit; passes → traces); `config/guardrails.yaml` versioned and hashed | P3 |
| 57 | PII v2 | Presidio (no NER) + GSTIN, UPI ID, card, Udyam recognisers; typed irreversible placeholders; regex fallback fails closed | P3 |
| 58 | Money-preservation gate | rupee figures never masked; 20,000-number Aadhaar checksum agreement; E4 re-run READY | P3 |
| 59 | Data classes + trace-leak test | C1–C4 tags; planted identifiers → 0 hits in traces; CSV formula escaping on exports | P3 |
| 60 | Retrieval dev split | 15–20 new labelled queries, never overlapping the frozen 40 | P0 |
| 61 | Contextual chunk headers | deterministic header on existing section chunks; chunk_ids stable; one re-ingest | P4 |
| 62 | Glossary query rewrite | deterministic expansion from a domain glossary | P4 |
| 63 | Answerability gate | abstain threshold tuned on the dev split | P4 |
| 64 | Span-cited answers + dual scoring | Critic cuts sentences without a valid span; strict + supported scores (ADR) | P5 |
| 65 | safety_v2 suite + A6 | 40 items frozen before first run; ≥38/40, 0 critical; guardrails-off ablation | P8 |
| 66 | OWASP LLM + ASI tests | one test per threat-model row | P8 |
| 67 | Fairness invariance | name/city/state invariance of gates, amount and ranking; protected-attribute denylist | P8 |
| 68 | RAI UI | AI-generated badge, approver attestation, safety panel | P9 |
| 69 | System card + threat model | SYSTEM_CARD, THREAT_MODEL (LLM + ASI), Sutra mapping (RBI + MeitY), DPDP gap note | P10 |

### Cut by plan v3.4 ([ADR 0032](../adr/0032-copilot-v2-scope-and-v34-cuts.md); rows above are kept, not deleted)
Stretch items not built: UI-09, UI-10, WC-08, VER-06, ONB-07, CP-04 (LW-15 built after all: [ADR 0037](../adr/0037-three-negotiation-rounds-and-reranking.md)). Deferred copilot items: full two-call CP-08, A7 guard-model ablation, adaptive red-team round (CP-07, CP-10, CP-11 and CP-12 were built in P13, [ADR 0035](../adr/0035-copilot-v3-product-assistant.md)). Reversible token vault replaced by irreversible placeholders.

## E. Decisions settled (no open questions block the build)
| Decision | Default now | Evidence or switch | ADR |
|---|---|---|---|
| APR annualisation | Nominal: periodic IRR × periods per year (not compounded) | Test reproduces RBI KFS Annex B illustration; `APR_CONVENTION=effective` kept only for sensitivity | 0012 |
| Reranker | `RERANKER=none` in core | `local_cross_encoder` (BAAI/bge-reranker-base) switched on if mentor approves; both reported in retrieval ablation | 0013 |
| Automated judge | Course model with J1, calibrated on 20% human labels | If Cohen's kappa < 0.7, free-text items are scored by humans only | 0014 |
| Demo mode | Live demo | Recorded video + replay profile prepared by W4 D3 as fallback | 0015 |
| Boundary at exactly ₹1.5 crore | `BOUNDARY_RULE=hold` | Configurable; audited | BRD APR-03 |

The only item a human must supply before Phase 0 is the owner names ([Name 1]…[Name 6], UI lead) in docs/REPO_STRUCTURE.md and CODEOWNERS.
