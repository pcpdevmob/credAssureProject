# CredAssure: Responsible AI, PII, AI Security, Guardrails and Copilot v2

**Plan update to BRD v3.1 · v3.4 (scoped to 50 hours)** · 17 November 2026 · Status: draft for team sync

> Design rule (unchanged): the model reads, explains and drafts. Code calculates, routes and gates. A human approves.
> Added: **every input, retrieval, tool call, output and trace passes through a guardrail written in code, and every block, redaction or flag is logged.**

---

## 0. What changed in v3.4

| Change | v3.3 | v3.4 | Why |
|---|---|---|---|
| Starting point | "Done: Phases 1–9c" | Done: Phases 1–9e, 10a, UI U1–U4, demo pack, G2. In progress: 10b | The plan was written against an old snapshot |
| Phase names | ★9d Guardrails, ★10b Copilot v2, ★11b, ★11S | **GR**, **CP2-R**, **CP2-A**, **SEC** | 9d (Critic), 9e (Copilot), 10a and 10b already exist in reports, commits and PROGRESS.md |
| Gap table | Said traces are unmasked and uploads unscanned | Corrected to what Phase 6 built (§2) | Guardrails are mostly **consolidation**, not new work |
| Added effort | ~75 h | **~50 h** (§9) | Fits the remaining weeks next to Phase 11, U5–U6, Phase 12 and the report |
| Copilot v2 | 8 enhancements (CP-05…CP-12) | **5 kept, all cheap or already built**; 5 deferred (§7) | 10/25 is retrieval-bound, so effort goes to retrieval only |
| Token vault | Reversible `[PAN_1]` tokens with a re-identification vault | **Irreversible typed placeholders** | The vault is new restricted storage and attack surface; synthetic data needs no re-identification |
| Guard model (A7), adaptive red-team round | Planned | **Stretch only** | Cost and quota; heuristic scorer + architecture stay the defence |
| Tuning data | Thresholds "tuned on the 40 queries" | **Tuned on a separate dev split only** | Tuning on the frozen set would contaminate the evaluation |
| Copilot regulatory target | ≥20/25 | **Strict ≥16/25, supported score reported beside it**, subject to mentor agreement | ≥20/25 needs the deferred answering work; we report the gap honestly |

## 1. Market trends that shape this plan (November 2026)

| Trend | What it means for CredAssure |
|---|---|
| OWASP Top 10 for Agentic Applications (ASI01–ASI10, Dec 2025), built around **least agency** | CredAssure's code-driven Supervisor with no write or accept tools is already least-agency; §5.2 makes that testable |
| OWASP LLM Top 10 (2026): injection and sensitive-information disclosure stay #1–#2; excessive agency #3 | §5.1 uses the 2026 numbering |
| "Assume the model will be fooled": architectural patterns over prompt filters (design-patterns paper, 2025) | CredAssure already uses four of the six patterns (§3.2) — a strong report section on small-model compensation |
| Guard models generalise unevenly on unseen prompts | Not used as a defence; A7 is a stretch ablation only |
| PII redaction before the LLM is standard; Presidio ships Aadhaar and PAN recognisers | Adopt Presidio behind our existing interfaces (§4) |
| DPDP Rules (Nov 2025, phased to May 2027); MeitY AI Governance Guidelines (Nov 2025) share RBI FREE-AI's seven Sutras | One Sutra mapping; DPDP stated as a production gap |
| RAG: retrieval is the bottleneck; contextual chunk headers, reranking and grounding gates are the 2026 defaults | Matches our diagnosis (10/25 retrieval-bound); §7 keeps exactly these |
| OpenTelemetry GenAI conventions (`gen_ai.*`) still in Development | Use the attribute names; keep Langfuse; don't over-invest |

## 2. Gap analysis (corrected against the build)

| Area | Already built | Real gap | Fix in this plan |
|---|---|---|---|
| PII | Aadhaar (Verhoeff checksum), PAN, IFSC, account, phone, email masked before every model call, on every reply, in logs and Langfuse traces, and in approver comments; uploads with Aadhaar/PAN/account refused (Phase 6); lender reply text masked (10b) | GSTIN, UPI ID, card, Udyam not covered; no data classes; no CSV-formula escaping; no trace-leak test over all planted identifiers | Presidio + Indian recognisers behind the same interface; data classes C1–C4; CSV escaping; trace-leak test (§4) |
| Guardrails | Injection scanner on uploads, KFS, lender replies, retrieved passages and citations; structured output + repair ×2; Critic; refusal rules; step/token caps; breaker; ToolRunner allowlist + loop detection; L3/L4 excerpt cap; citation isolation (404) | Controls spread across `packages/llm`, `packages/core`, gateway and adapters; decisions not logged as one event type; no single policy file | Consolidate into `packages/guardrails` (R1–R5), `guardrail_event`, `config/guardrails.yaml` (§3) |
| AI security | BR-15; `corpus.lock`; bandit, pip-audit, npm audit; Schemathesis fuzzing; security-reviewer on every phase; step-up approval; nginx headers | No written threat model or OWASP/ASI mapping; Markdown/HTML sanitisation not enforced by test; CSP; login rate limit | §5 |
| Responsible AI | Human-in-the-loop boundary; maker-checker; step-up; append-only audit with tombstones; no accept/sign tool; `LLM_ENABLED=false`; blocker codes | System card; fairness evidence; AI labels; approver attestation; Sutra mapping | §6 |
| Copilot | Hybrid BM25 + dense, RRF, ADR 0019 filters, citation passage panel, abstention, refusal 8/8, injection 8/8, isolation 3/3; reranker built but off (ADR 0013) | Recall@5 24/40; regulatory 10/25 (6 "wrong document" passes, 2 superseded sources fixed in 10b) | §7 (retrieval only) |

## 3. Guardrail architecture

### 3.1 Rails

```
 User chat / upload / approver action
        │
 [R1 INPUT]  authz + role · size/rate limits · schema validation · PII detect → placeholder/block
             · injection scorer · scope classifier (SUP-02)
        ▼
   Supervisor (code: fixed plan) ──► Agent
                                       │
 [R2 RETRIEVAL]  server-side case + tenant filter · effective date/jurisdiction (ADR 0019)
                 · datamark untrusted text · flag instruction-like spans · excerpt cap by legal basis
                                       │
                                    ≤8B model
                                       │
 [R3 TOOL]  per-agent allowlist · JSON-schema args · case_id injected by server · read-only tools
            · step/token budget · loop detection
                                       │
 [R4 OUTPUT]  schema validate/repair ×2 · Critic (numbers vs ledger, citation spans, grounding gate)
              · banned content · PII re-scan · Markdown/HTML sanitise · "AI-generated" label
                                       │
 UI / report / API
 [R5 TELEMETRY]  mask before Langfuse export · gen_ai.* span attributes · hashed user IDs
```

| Decision | Choice | Why |
|---|---|---|
| Framework | In-house `packages/guardrails`, built by **moving existing code behind the same interfaces** | No extra model calls on the quota; existing tests stay the safety net |
| Layering | `core` ← `guardrails` ← `llm` / `adapters` / gateway; agents never import `llm` (ADR 0006) | New import-linter contracts in the guardrails ADR |
| Injection detection | Heuristic scorer (English + Hindi/Hinglish phrases, encoding tricks). Guard model: stretch A7 only | Guard models generalise unevenly; architecture makes a successful injection harmless |
| Policy | `config/guardrails.yaml`, versioned and hashed like the prompt registry | Drift caught by `make eval-fast` |
| Failure mode | Fail closed | PII detector error → don't store; scorer error → suspicious; output rail error → fixed template |
| Evidence | `guardrail_event {rail, rule_id, action, case_id, trace_id}`: **blocks, redactions and flags** to the audit log; passes to traces only | Evidence without flooding the hash chain |

### 3.2 Prompt-injection design patterns already in CredAssure

| Pattern | Where | Test that makes it explicit |
|---|---|---|
| Plan-then-execute | Stage order fixed in code before any document is read (SUP-01) | A KFS saying "skip to approval" leaves the plan unchanged (G3) |
| LLM map-reduce | LendWise audits one offer per call; code merges and ranks | One poisoned KFS doesn't change another offer's result |
| Context-minimisation | Narratives see ledger facts only, never raw documents or chat | Narrative calls carry no user prompt or raw text |
| Action-selector | Copilot refusal/abstention routing is code, not model text | Router output is an enum (full CP-10 tools deferred) |

## 4. PII and data handling

### 4.1 Data classes

| Class | Examples | To model? | To traces? | Storage |
|---|---|---|---|---|
| C1 Public | RBI directions, Acts, schemes | Yes | Yes | corpus.db, Chroma |
| C2 Internal | Synthetic policies, prompts | Yes | Yes | repo |
| C3 Confidential | Case financials, offers, KFS | Active case only | Ledger references only | case.db |
| C4 Restricted | Aadhaar, individual PAN, account/card numbers, mobile, email, UPI ID, DOB, home address | **Never** | **Never** | hr.db only; placeholders elsewhere |

### 4.2 Engine

- **Presidio Analyzer** with no NER model (or the small spaCy model only), plus custom recognisers: GSTIN (check digit), UPI ID (PSP handle list), card (Luhn), Udyam number (C3). Existing Aadhaar (Verhoeff), PAN, IFSC + account, mobile and email logic is kept or ported.
- **Typed, irreversible placeholders** (`[PAN]`, `[MOBILE]`). No re-identification vault: data is synthetic and the vault would be new C4 storage.
- **Money-preservation gate (blocking):** rupee figures are never masked. Presidio must pass the existing 20,000-number Aadhaar checksum agreement test and the money fixtures, and the E4 re-run must stay READY, before it replaces the regex path.
- **Fallback:** the existing regex + checksum code stays as a zero-dependency path; if Presidio fails to load, fail closed.
- Employee names: exact match against hr.db → `EMP-xxx` before any model call.

**Where the scan runs:** chat and every uploaded cell (R1), retrieved text (R2), every model output (R4), the trace export hook (R5).

### 4.3 Handling rules
- Data minimisation: Onboarding sends rule results and employee IDs only (BR-14).
- Trace test: search traces for every planted identifier → 0 hits.
- Retention: `DELETE /v1/cases/{id}` with audit tombstone (built in 10a); audit holds no C4 data by construction.
- Exports: escape cells starting with `= + - @`.
- Report wording: synthetic data only; a production version is a DPDP data fiduciary with obligations phasing in to May 2027 — a stated production gap, not a compliance claim.

## 5. AI security

### 5.1 OWASP Top 10 for LLM Applications (2026)

| Risk | Control | Test |
|---|---|---|
| LLM01 Prompt injection | Datamarking; §3.2 patterns; scorer; Critic | 8 frozen + 12 in safety_v2 |
| LLM02 Sensitive information disclosure | §4; case and tenant isolation | 10 PII + 3 isolation |
| LLM03 Excessive agency | Allowlist; read-only tools; no accept/sign/approve tool; maker-checker; step-up | 6 agency items |
| LLM04 Supply chain | Lock files; audits; model digest pinned; SBOM | CI / pre-push |
| LLM05 Data and model poisoning | Source allowlist; `corpus.lock`; ingestion scanner | Planted poisoned document |
| LLM06 Unbounded consumption | Caps, rate limits, breaker, upload limits | Flood items |
| LLM07 Misinformation | Ledger, Critic, grounding gate, date filters, superseded tags | Regulatory + KR-04 |
| LLM08 Hidden context exposure | No secrets in prompts; refusal; leakage check | 3 items |
| LLM09 Vector and embedding weaknesses | Server-side filters only; citation 404 isolation | Cross-case KFS check |
| LLM10 Improper output handling | Plain-text rendering, `rehype-sanitize` where Markdown is rendered, CSP | 4 items |

### 5.2 OWASP Top 10 for Agentic Applications (ASI, 2026)

| ASI risk | Control |
|---|---|
| ASI01 Goal hijack | Plan fixed in code; agents return typed results, never next steps |
| ASI02 Tool misuse | Per-agent allowlist; schema args; read-only; server-injected case_id |
| ASI03 Identity and privilege abuse | Agents hold no credentials; approval needs a human JWT with the routed role + step-up |
| ASI04 Agentic supply chain | Hashed prompt registry; pinned model digest; no dynamic tools or MCP servers |
| ASI05 Unexpected code execution | No code-exec tool; model output never executed |
| ASI06 Memory and context poisoning | Only code engines write the ledger; flagged chat turns not fed back |
| ASI07 Insecure inter-agent communication | Agents never call each other; hand-offs via Supervisor and `AgentResult` (ADR 0018) |
| ASI08 Cascading failures | Per-stage fail-closed gates; re-check on every GO; breaker |
| ASI09 Human-agent trust exploitation | Critic findings first; approver attestation; AI labels; Critic blocks approval predictions |
| ASI10 Rogue agents | Step/token caps; `LLM_ENABLED=false` kill switch; per-agent flags |

### 5.3 Application security and red-teaming
- CSP and security headers, JWT expiry and refresh, login rate limit, upload MIME and size checks; `security-reviewer` sign-off on PRs touching `apps/gateway` or `packages/guardrails`.
- Red-teaming: the frozen 20-prompt log (unchanged) + the frozen **safety_v2** suite (§8). The adaptive mutation round is **stretch**.

## 6. Responsible AI

| Principle | Control | Evidence |
|---|---|---|
| Human oversight | No approve/accept/sign capability; maker-checker; step-up; **approver attestation** that Critic findings were reviewed | APR-04/05; UI test |
| Fairness | No credit scoring; upload schemas reject protected-attribute fields | **Invariance tests:** change promoter name, city and state → identical gates, amount and ranking (copilot text may differ legitimately because of the ADR 0019 jurisdiction filter) |
| Explainability | Reason codes per gate linked to ledger facts and citations | UI |
| Transparency | "AI-generated draft" badge; copilot shows sources and "as of" date; abstains when ungrounded | UI review |
| Accountability | Append-only audit with verify; guardrail events logged; RACI in the system card | Audit verify |
| Safety and resilience | Fail closed; kill switch; template fallback | Demo with model off |
| Privacy | §4 | PII + trace tests |

**Sutra mapping:** RBI FREE-AI (Aug 2025) and MeitY's India AI Governance Guidelines (Nov 2025) share seven Sutras; the report maps each to the controls above, framed as alignment by design for a prototype, not compliance.

**System card** (`docs/SYSTEM_CARD.md`): intended use and users · out-of-scope uses · models · data provenance (L1–L5) · human-in-the-loop boundary · refusal policy · guardrail layers and patterns · OWASP LLM + ASI mapping · evaluation and adversarial results · failure taxonomy · limitations · contact.

## 7. Copilot v2 (reduced scope)

The copilot's live misses are retrieval misses: the expected document reaches the top 5 for only 10 of 19 answerable questions, which caps the score near 16/25 however good the answers are. So v3.4 spends copilot time only on cheap retrieval and grounding work, and uses what is already built.

### 7.1 Kept (9 h retrieval + 4 h answering)

| # | Enhancement | Detail | Hours |
|---|---|---|---|
| CP-06 | **Contextual headers** on the existing section chunks | Prepend a deterministic header (issuer · document title · section · effective date) before embedding. **Chunk boundaries don't change, so `chunk_id`s stay stable** and stored citations still resolve. One re-ingest. | 3 |
| CP-05 | **Deterministic glossary rewrite** | Expand KFS, APR, CGTMSE, MSE, TReDS, Udyam, EBLR, MCLR, GST, NBFC from a domain glossary — never built from test queries. No model call. | 2 |
| CP-07b | **Reranker** | Turn on the reranker already built behind ADR 0013, only if the mentor allows a local model | 1 |
| CP-09 | **Answerability gate** | Abstain below a rerank/fusion score threshold tuned on the **dev split** | 2 |
| — | Retrieval ladder report | Frozen 40: baseline → +headers → +rewrite → +reranker | 1 |
| CP-08-lite | **Span-cited answers** | Every answer sentence must carry a valid span ID from the retrieved passages; the Critic cuts any sentence without one. One call, not a separate extract step. | 3 |
| — | **Dual strict/supported scoring** (ADR) | Strict = cites the gold document; supported = cites a valid, current document that supports the answer (judge + human sample). Both reported; strict stays the headline. | 1 |

### 7.2 Deferred (future work in the report)

CP-07 intent → collection routing · CP-08 full two-call extract-then-answer · CP-10 case-aware tools · CP-11 case memory · CP-12 streaming, follow-ups and feedback · A7 guard model · adaptive red-team round.

### 7.3 Targets

| Metric | Now | v3.4 target |
|---|---|---|
| Retrieval recall@5 (frozen 40, v1.0 labels) | 24/40 | **≥ 30/40** (34 stretch) |
| Copilot regulatory, strict | 10/25 | **≥ 16/25**, supported score reported |
| False abstain | — | ≤ 3/25 |
| Refusal / injection / isolation | 8/8 · 8/8 · 3/3 | unchanged |

The BRD target of ≥20/25 is not expected within this scope. It goes to the mentor as a decision; if it stays, the gap is reported with the retrieval diagnosis and the deferred list.

## 8. Evaluation changes

The frozen 100-item set is **not edited**. New items go in a separately frozen suite with its own ADR.

| Suite | Items | Target |
|---|---|---|
| Frozen v1 (unchanged) | 100 | ≥ 92 and above the best baseline |
| **safety_v2** | 40: PII 10 · injection 12 (KFS, CSV field, corpus, chat, Hinglish, encoded) · agency/ASI 6 · hidden context 3 · output handling 4 · fairness invariance 5 | ≥ 38/40, **0 critical** |
| Retrieval dev split | 15–20 new queries, never in the frozen 40 | Used for tuning only |
| Retrieval | 40 queries | ≥ 30 in top 5 |
| Copilot regulatory | 25 (from frozen v1) | Strict ≥ 16, supported reported |

**Ablations added:** A6 guardrails off (R1/R2/R4) on safety_v2; copilot retrieval ladder. A7 only as stretch.

**Telemetry:** spans carry `gen_ai.*` attributes; the trace dashboard shows block rate, redactions, injection flags, abstention rate, Critic fallback rate and tokens per stage.

## 9. Revised phases (remaining work)

Done: Phases 1–9e, 10a, UI U1–U4, demo pack, G2. In progress: 10b. Hours are **added effort** over the original BRD plan; base-plan phases are not counted.

| Order | Phase | Scope | Owner | Added h | Exit check |
|---|---|---|---|---|---|
| 0 | **P0 Plan + ADRs** | Adopt v3.4; ADRs (guardrails layering, PII policy, safety_v2, copilot scope + dual scoring); retrieval dev split; mentor questions | Pritish, Suresh | 4 | ADRs Proposed; dev split labelled |
| 1 | **G1 close** (team, parallel) | Judging + kappa, hand check, APR transcription, names, ADR 0018, `/freeze-g1` | Team | — | G1 ticked |
| 2 | **G3** (extended) | `/gate G3`, E18, plan-then-execute and map-reduce injection tests | Integration lead, Abhishek | 2 | G3 ticked, 0 MUST |
| 3 | **GR Guardrails + PII v2** | Consolidate into `packages/guardrails`; R1–R5 + `guardrail_event` + policy YAML; Presidio + 4 recognisers; money gate; data classes; CSV escaping; trace test; `gen_ai.*` | Pritish | 10 | One case end to end with rail events; 0 planted identifiers in traces; E4 READY |
| 4 | **CP2-R Copilot retrieval** | Headers, glossary rewrite, reranker if allowed, answerability gate, ladder | Suresh | 9 | Recall@5 ≥ 30/40 locally |
| 5 | **CP2-A Copilot answering-lite** | Span-cited answers; dual scoring | Tejas | 4 | Regulatory strict ≥ 16/25 |
| 6 | Course endpoint switch | Probe, graded baseline, one re-embed, re-run retrieval and regulatory | Pritish | — | Both models recorded |
| 7 | Phase 11 | Harness, taxonomy, J1, A1–A5 | Abhishek, Tejas | — | ≥ 92/100, above baseline |
| 8 | **SEC Security + safety_v2** | safety_v2 frozen; OWASP/ASI tests; fairness invariance + denylist; CSP, JWT, login rate limit, sanitisation; A6 | Abhishek, Tejas | 12 | safety_v2 ≥ 38/40, 0 critical |
| 9 | U5 (+ RAI UI) – U6 | Base scope + AI badge, approver attestation, safety panel | UI lead | 3 | UI review 0 MUST |
| 10 | Phase 12 + **RAI docs** | Base scope + system card, threat model, design patterns, Sutra mapping, DPDP gap | Pritish + all | 6 | Report RAI section complete |
| 11 | G4 | `/eval app` + safety_v2 + guardrail metrics; live safety moment in demo | All | — | Rehearsed demo |

**Added effort: 50 hours** (range 40–60 with the cut list below). Paid for by dropping stretch items UI-09/10, WC-08, LW-15, VER-06, ONB-07, and by deferring the copilot items in §7.2.

**Cut order if G3 slips** (saves up to ~9 h, floor ≈ 41 h): reranker experiment (1) → glossary rewrite (2) → dual scoring (1) → A6 ablation (1) → fairness invariance reduced to 3 cases (1) → RAI UI reduced to AI badge + attestation (1) → OWASP/ASI tests limited to mapping existing tests (2).
**Never cut:** PII v2 core and money gate, trace masking, output sanitisation, safety_v2, the OWASP + ASI mapping, contextual headers, the system card.

## 10. ADRs and open questions

**ADRs** (next free numbers): guardrail pipeline, layering and fail-closed policy · PII policy, data classes and Presidio · safety_v2 suite · Copilot v2 reduced scope and dual strict/supported scoring · injection design patterns as architecture.

**For the mentor:**
1. May we enable the local cross-encoder reranker (built, off by ADR 0013)?
2. Is a separately frozen safety_v2 suite acceptable?
3. Can the system card sit in an appendix outside the 12 pages?
4. Copilot regulatory: keep ≥ 20/25, or accept strict ≥ 16/25 with the supported score and retrieval diagnosis reported?

**For the team sync:** confirm owners (GR Pritish, CP2-R Suresh, CP2-A Tejas, SEC Abhishek + Tejas) and the stretch cuts.

## Sources
- OWASP Top 10 for Agentic Applications 2026: https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agent
- OWASP Top 10 for LLM Applications 2026: https://aembit.io/blog/the-owasp-top-10-for-llm-applications-2026-what-changed-and-why-it-matters/
- Design Patterns for Securing LLM Agents against Prompt Injections: https://arxiv.org/abs/2506.08837
- Guard models: https://arxiv.org/pdf/2511.22047v1
- Presidio predefined recognisers: https://tessl.io/registry/tessl/pypi-presidio-analyzer/files/docs/predefined-recognizers.md
- MeitY India AI Governance Guidelines: https://casrai.org/guides/india-ai-governance-guidelines
- RBI FREE-AI: https://kpmg.com/in/en/insights/2025/08/rbi-free-ai-committee-report-on-framework-for-responsible-and-ethical-enablement-of-artificial-intelligence.html
- DPDP Rules 2025: https://www.mondaq.com/india/data-protection/1708434/
- OpenTelemetry GenAI conventions: https://www.dash0.com/knowledge/opentelemetry-genai-semantic-conventions-explained
