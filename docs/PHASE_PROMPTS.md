# CredAssure — Phase Prompts for Cursor

Paste one phase per Cursor Agent session (start in Plan mode, approve, then Agent mode).
Each phase ends with `make check` green. Phases map to BRD §15 weeks and gates.

---

## Phase 0 — Scaffold (Week 1, day 1)

Scope items built in this phase (docs/BUILD_SCOPE.md): #30 Config + feature flags; #31 Structured logging; #42 Ownership and review; #43 Architecture records; #44 Environment profiles.
```
Create the repository skeleton exactly as in docs/REPO_STRUCTURE.md (ADR 0005); architecture in docs/architecture/ARCHITECTURE.md.
- pyproject.toml with uv; Python 3.12; deps: fastapi, uvicorn[standard], pydantic>=2, pydantic-settings,
  sqlalchemy>=2, alembic, langgraph, langgraph-checkpoint-sqlite, openai, chromadb, langfuse, streamlit,
  httpx, pyjwt, argon2-cffi, slowapi, jinja2, pyyaml, tenacity, sentence-transformers (optional extra "rerank").
  Dev: pytest, pytest-cov, hypothesis, ruff, mypy, bandit, pip-audit, pre-commit, numpy-financial (eval only).
- src/credassure/config.py with pydantic-settings for every variable in CURSOR_MASTER_PROMPT.md; fail fast
  if LLM_BASE_URL or JWT_SECRET is missing outside test mode.
- Makefile targets: install, check (ruff, mypy --strict src, pytest -q, bandit -r src), check-fast (ruff + pytest -q -m "not slow"),
  test, run-api, run-ui, data, ingest, eval, baseline, openapi (export openapi.json; ADR 0004), demo-reset.
- .pre-commit-config.yaml: ruff, ruff-format, mypy, bandit, gitleaks.
- .gitignore: .env, *.db, data/corpus/raw/, data/corpus/text/, chroma/, .cache/.
- .env.example with every key, no values.
- GitHub Actions workflow running make check + pip-audit.
- docs/adr/0001-stack.md and docs/adr/0002-threat-model.md (STRIDE table over UI, API, agents,
  documents, LLM endpoint, data stores).
Acceptance: `make install && make check` passes on an empty test suite with one smoke test.
```

## Phase 1 — Shared contract, money, normaliser (Week 1; FREEZE at G1)

Scope items built in this phase (docs/BUILD_SCOPE.md): #8 Rounding policy; #9 Blocker catalogue; #24 Agent registry + data-access matrix; #25 Agent versioning + stage retry; #26 ADR on excluded patterns; #32 Error catalogue; #46 Hexagonal agents.
```
Implement src/credassure/domain/: enums.py, money.py, results.py (AgentResult, Blocker, EvidenceRef as in
design-detail §2.1), schemas/ for case files, offers, HR and KFS (schema_version "1.0").
money.py: Decimal context; to_paise/from_paise; format_inr() with Indian grouping; round_up_to_lakh().
engines/normaliser.py (VER-01): parse "₹1,42,00,000", "1.42 crore", "142 lakh", "1.42 Cr", "Rs. 142L",
"12%", "0.12", "12 percent", dates in ISO and DD-MM-YYYY / DD/MM/YYYY. Return typed values with the
original span. Write 50+ parametrised tests plus hypothesis round-trip tests (format → parse → equal).
Acceptance: mypy strict clean; ≥50 normaliser tests; ADR noting the contract is frozen.
```

## Phase 2 — Synthetic data generators (Week 1)

Scope items built in this phase (docs/BUILD_SCOPE.md): #14 Corpus legal-basis audit.
```
Implement data/generators/ per docs/DATA_SPEC.md §1–5: hr.py (→ hr.db), cases.py, offers.py, kfs.py,
policies.py, lender_scripts.py. Seeded via CREDASSURE_SEED; parameter ranges documented at the top of each
file. Output to data/frozen/v1/. Generate the planted distributions EXACTLY as tabled, and write a
data/frozen/v1/PLANTS.md listing each planted item ID and its plant type.
Constraints: no LLM calls; no real names, IDs or PII; KFS docs as Markdown text; injection plants as specified.
Do NOT import src/credassure/engines here — generators choose inputs; they do not compute gold answers.
Acceptance: `make data` is idempotent (same seed → identical bytes, checked by a test hashing outputs).
```

## Phase 3 — Eval set, independent gold, baseline (Week 1; G1)

Scope items built in this phase (docs/BUILD_SCOPE.md): #13 Eval reproducibility record.
```
Implement eval/:
- gold/: independent calculators (float + numpy_financial allowed) that compute expected funding need,
  APR, ranking, affordability and route for each case/offer. MUST NOT import src/credassure/engines.
- testset/v1/items.jsonl: 100 items with the BRD §13 category counts, schema in DATA_SPEC §7.
- retrieval/v1/queries.jsonl: 40 labelled queries (labels by doc_id + section_path).
- scorers.py: exact_money (₹1), exact_rate (0.01 pp), exact_enum, ranking, citation_valid, refusal, judge.
- baseline/s1_structured.py, s2_cot_vote.py (5 samples, majority), s3_decompose.py: one prompt attempts
  every item against the raw LLM; record schema failures, arithmetic errors, wrong gates, invented
  citations, injection compliance into eval/baseline/results/*.jsonl and a summary table.
- A freeze script that writes SHA-256 of testset files to eval/FROZEN.sha256; a test fails if they change.
Acceptance: baseline runs end to end; summary table printed per category and failure class.
```

## Phase 4 — Deterministic engines (Week 2)

Scope items built in this phase (docs/BUILD_SCOPE.md): #1 Ablation switch paths; #7 Repayment date → week mapping.
```
Implement src/credassure/engines/ as PURE functions per .cursor/rules/20-money-and-calculation.mdc:
cashflow.py (WC-03..06): weekly table over FORECAST_WEEKS, confirmed receipts only, peak shortfall + week +
duration, recommendation formula, bridge from indicative amount that sums exactly.
validators.py (WC-01/02): missing fields → Blocker naming field; duplicates, unit/currency, totals,
cross-file consistency.
loancost.py (LW-05..08): amortisation schedule (emi and equal_principal, moratorium), GST on all fees,
insurance, CGTMSE on sanctioned/outstanding, borrower cash-flow vector, Decimal IRR (Newton + bisection),
APR per APR_CONVENTION, amount received, total repayment, total cost; RATE_MAY_RESET flag.
offer_audit.py (LW-02/03): material-term checklist; instalment recompute with ₹1 tolerance.
affordability.py (LW-09/10): overlay disbursal + instalments on the cash table; NOT_AFFORDABLE, LATE_OR_SHORT.
ranking.py (LW-11): comparable ∧ affordable; APR, then total cost, then availability.
onboarding_rules.py (ONB-02/03) using AS_OF_DATE.
routing.py (APR-01..03): threshold + BOUNDARY_RULE.
Tests: known-answer tests against eval/gold for all 15 cases and 45 offers; hypothesis properties
(bridge sums; recommendation ≥ 0; APR ≥ nominal rate when fees > 0; ranking never puts an unaffordable
offer first; routing monotonic). Routing boundary ±₹1 tests call route() directly.
Acceptance: 15/15 cash-flow and 15/15 offer known-answer cases pass; coverage ≥ 95% on engines/.
```

## Phase 5 — Database, ledger, audit, auth (Week 2)

Scope items built in this phase (docs/BUILD_SCOPE.md): #22 Concurrency; #27 Multi-tenancy readiness; #29 Migrations; #49 Transactional audit.
```
Implement src/credassure/db/ models and Alembic migrations for case.db and corpus.db exactly as
design-detail §4; hr.db access via a read-only engine (mode=ro URI) with no write methods.
ledger/fact_ledger.py: put(case_id, key, value, unit, source_type, source_ref, produced_by, input_hash)
→ new version; get_latest; list_for_case. Values stored as text Decimal or paise.
ledger/audit_log.py: append-only with hash chain; SQLite triggers blocking UPDATE/DELETE; verify_chain().
security/authz.py: argon2 hashing, JWT issue/verify, role dependencies, case-visibility check.
Seed users: 2 preparers, 1 director_finance, 1 vp_finance, 1 evaluator (passwords from env for demo).
Tests: UPDATE/DELETE on audit_log raises; tampering detected by verify_chain; HR writes impossible;
case isolation (user A cannot read case of user B) — SUP-08 3/3.
```

## Phase 6 — LLM layer and security modules (Week 2)

Scope items built in this phase (docs/BUILD_SCOPE.md): #22 Concurrency; #23 Timeouts and cancellation; #36 Prompt/model change control; #48 Model resilience.
```
Implement src/credassure/llm/: client.py (OpenAI SDK pointed at LLM_BASE_URL; tenacity backoff, max 2
retries; token-budget guard; SQLite-backed response cache keyed by model+prompt_version+messages hash;
Langfuse span with masked I/O), structured.py (schema-in-prompt + few-shot; parse; repair ≤2; else raise
StructuredOutputError), prompts/registry.py (YAML prompts with name, version, template; sha256 recorded),
budget.py, ratelimit.py.
security/pii.py (Aadhaar with Verhoeff, PAN, IFSC, account numbers near keywords, phone, email),
security/spotlight.py (random delimiter + datamark every passage; returns wrapped text + source map),
security/injection.py (heuristic scanner: role-switch phrases, "ignore previous", tool/route words,
encoded payloads) returning flags.
tests/conftest.py: FakeLLM fixture with scripted replies keyed by prompt name.
Tests: PII redaction suite; repair path; budget breach → error; cache hit on repeat.
```

## Phase 7 — Retrieval and copilot search (Week 2; KR-01..05)
```
Implement data/corpus/download.py (reads manifest.yaml, throttled ≤1 req/s, sha256, text extraction,
drops unreadable PDFs with a log) and src/credassure/retrieval/:
chunking.py: three strategies — fixed512 (512 tokens, 64 overlap), section (heading-aware), semantic
(split on embedding-similarity drops). ingest.py: documents/chunks rows, FTS5 index, Chroma collection
per strategy, injection scan per chunk. filters.py: collection, jurisdiction=IN, effective date ≤ AS_OF and
not superseded, case_id match for KFS. fusion.py: reciprocal-rank fusion (k=60). rerank.py: top-30 → top-5
via RERANKER setting. Tool: search_knowledge(query, case_id, filters) → passages with chunk_id, doc title,
section, effective date.
eval/retrieval_eval.py: recall@5 and recall@10 for {BM25, dense, hybrid} × {3 chunkings} × {rerank on/off};
write eval/reports/retrieval_week2.md.
Acceptance: ≥500 documents indexed; report generated; target 34/40 with a relevant passage in top 5.
```

## Phase 8 — Walking skeleton (mid-Week 2 checkpoint)

Scope items built in this phase (docs/BUILD_SCOPE.md): #1 Ablation switch paths; #4 Loop detection; #15 Full-case CI test with FakeLLM; #16 Endpoint health + quota monitor; #28 API versioning; #46 Hexagonal agents; #47 Async stage jobs; #50 Health probes.
```
Implement the Supervisor LangGraph (design-detail §2.2 and §2.4.1; routing is a code node, not an agent) with SqliteSaver, placeholder agents that return
canned AgentResults via the real contract, the deterministic re-check hook (SUP-05), step/token caps,
pause-with-question and resume-only-blocked-stage (SUP-06), and the interrupt for approval.
Implement FastAPI routers for every endpoint in design-detail §3.1 with role dependencies, RFC 9457 errors,
X-Request-ID, slowapi limits, 2 MB upload cap and schema validation with field/row/reason errors.
Minimal Streamlit: login, create case, upload, run, stage tracker — all through ui/api_client.py.
Also: per-step endpoints POST /cases/{id}/readiness|assessment|verify|proposal as thin wrappers that run one
Supervisor stage (ADR 0003 §8); gates enforced server-side so no endpoint skips a gate; LLM_ENABLED=false mode
where all gates, calculations, routing and approval still work and narratives use templates (ADR 0003 §2).
If the team keeps the existing FinBridge AI UI (ADR 0003 open decision), replace its mock services with this API
instead of building Streamlit pages.
Acceptance: the main demo case runs end to end through API and UI with placeholders and one Langfuse trace,
with LLM_ENABLED=true and false. Target end of Week 1, not mid-Week 2.
```

## Phase 9 — Agents (Weeks 2–3). One prompt per owner.

Scope items built in this phase (docs/BUILD_SCOPE.md): #25 Agent versioning + stage retry.

### 9a Employee Onboarding Agent

Scope items built in this phase (docs/BUILD_SCOPE.md): #25 Agent versioning + stage retry.
```
Implement agents/onboarding per design-detail §2.4.2 and BRD §8.3 (ONB-01..06). Tools: get_hr_profile,
evaluate_onboarding_rules. The model only writes the plain-language explanation of failed rules and next
actions (prompt onboarding_explain v1), never the decision. Redact PII in chat (ONB-06). Feature-flagged
ONB-07 checklist with policy citations.
Acceptance: 10/10 onboarding eval items; every failed rule named in the explanation (Critic check).
```

### 9b Working Capital Advisory Agent

Scope items built in this phase (docs/BUILD_SCOPE.md): #25 Agent versioning + stage retry.
```
Implement agents/working_capital per design-detail §2.4.3 (WC-01..07). Flow: validate files → if blockers, NEEDS_INPUT with ONE
focused question (choose the highest-priority blocker by code) → compute cash table and recommendation →
write ledger facts (peak_shortfall, peak_week, shortfall_weeks, min_buffer, undrawn_limits, mitigations,
recommended_amount, bridge lines) → model drafts driver explanation using ONLY ledger keys passed in the
prompt (prompt wc_explain v1). Optional LLM header-mapping step when CSV headers differ (map to schema
fields from a fixed list; code validates).
Acceptance: 15/15 known-answer cases through the API; bridge sums exactly; no unsourced offset.
```

### 9c LendWise Agent

Scope items built in this phase (docs/BUILD_SCOPE.md): #25 Agent versioning + stage retry.
```
Implement agents/lendwise exactly as design-detail §2.4.4 and §2.4.7 (LW-01..14). One offer per LLM call for KFS charge
extraction (prompt lw_kfs_extract v1, output KfsChargeExtraction); discard any extraction whose source_span
is not a verbatim substring of the KFS text. Price, audit, affordability and ranking are tool calls to
engines. Negotiation round 1 as a separate invocation using template fee_waiver_v1 with slots filled only
from ledger facts; Critic must pass before send; lender simulator returns a new version; re-audit and
re-price before any concession appears anywhere. Gate: GO iff ≥2 comparable AND affordable offers.
Write ledger facts per offer: amount_received, total_repayment, total_cost, apr, flags, rank.
Feature-flagged LW-15 (rounds 2–3).
Acceptance: 15/15 offer eval items; 5/5 negotiation-safety items; planted hidden charges, mismatches,
unaffordable-cheapest and guarantee-fee offers all caught; injection lines in KFS/lender replies have no effect.
```

### 9d Verification Critic

Scope items built in this phase (docs/BUILD_SCOPE.md): #21 Critic → agent feedback contract; #25 Agent versioning + stage retry.
```
Implement agents/critic per design-detail §2.4.5 (VER-01..05). verify_claims: extract every amount, percentage and date from text
via the normaliser and match to ledger facts for the case (exact for money to ₹1, rates to 0.01 pp);
verify every citation's chunk_id exists, belongs to an allowed collection/date, and the quoted span or
claim keywords appear in it; banned-content scan (acceptance/signing language, approval predictions,
invented rates, false urgency, PII); report completeness against the required section list.
Regenerate ≤2 then render the fixed template (reports/templates/fallback_*.j2). Record fallback rate.
Acceptance: planted bad claims and fabricated citations blocked; safety tests pass.
```

### 9e Ask CredAssure Copilot

Scope items built in this phase (docs/BUILD_SCOPE.md): #2 Copilot conversation state; #20 Model-directed tool selection in core; #25 Agent versioning + stage retry.
```
Implement agents/copilot per design-detail §2.4.6 (CP-01..03); it is on demand via chat, not a pipeline stage: refusal policy check first (BRD §14 table, code + classifier),
then classify → search_knowledge → rerank → answer with [chunk_id] citations from ≤5 spotlighted passages;
numbers only from get_case_facts; Critic must pass; otherwise return exactly
"I can't verify that from the available sources." Feature-flagged CP-04 planner.
Acceptance: ≥20/25 regulatory items with valid citation; 8/8 refusal; 8/8 injection; 3/3 isolation.
```

## Phase 10 — UI, approvals, reports (Week 3)

Scope items built in this phase (docs/BUILD_SCOPE.md): #6 Proposal versioning / staleness; #10 Required report sections config; #33 Explainability endpoint; #39 Data deletion workflow; #40 Chat notice and consent; #51 API fuzzing; #53 Architecture conformance check.
```
Per ADR 0004 the UI is replaceable: build only a thin reference Streamlit client via ui/api_client.py, no business
logic in ui/, and add contract tests in tests/contract/ for every endpoint. Pages: funding view (cash chart, need vs ₹2 cr, bridge), offer comparison (APR, total
cost, net disbursal, flags, non-comparable/unaffordable marked), copilot chat with clickable citations
opening the passage, approval inbox (only routed role; approve/reject/return-to-stage with comment),
report export (Markdown/HTML via Jinja2 autoescape) including decision history and trace IDs, evaluator
pages (runs, scores). APR-04..06 enforced server-side. Report states approval is internal, not acceptance. Proposal versioning: any change to an upstream ledger fact marks
the proposal stale and requires a new version (ADR 0003 §3).
```

## Phase 11 — Evaluation, ablations, red-team (Weeks 3–4)

Scope items built in this phase (docs/BUILD_SCOPE.md): #1 Ablation switch paths; #5 Cost per query; #11 Judge calibration; #12 Failure-class tagging; #34 Graceful degradation matrix; #35 Performance smoke.
```
eval/harness.py runs the 100 items through the API, stores eval_results with failure_class, tokens,
latency, trace_id. ablations.yaml: A1 model calculates; A2 ledger+Critic off; A3 dense top-5 only;
A4 model decides gates in free text; A5 injection defence off — each with its affected categories only.
report.py: per-category table for baseline (best of S1–S3), full system, each ablation; failure taxonomy;
judge agreement on a 20% human sample; tool calls/task, tokens and latency per stage.
docs/redteam_log.md with 20 prompts, outcome, fix.
Acceptance: ≥92/100 and above best baseline; effects claimed only if seen in >1 category or on rerun.
```

## Phase 12 — Ship (Week 4)

Scope items built in this phase (docs/BUILD_SCOPE.md): #3 Model card / responsible AI; #17 Demo resilience; #37 Release management; #38 Backup / restore; #41 Supply-chain evidence; #45 Runbook; #53 Architecture conformance check.
```
Dockerfile (multi-stage, non-root user, no secrets baked in) and docker-compose.yml (api, ui, volumes for
db and chroma; healthchecks). `docker compose up` brings up everything; ingestion via `make ingest`.
Cached replay mode (REPLAY_MODE=true) serving the main case from recorded LLM responses for demo resilience.
Quota alerts at 70%/90%. `make demo-reset` restores seeded, blocked and happy-path cases.
Days 19–20: freeze; defect triage blockers → wrong figures → display; rehearse 8–10 min demo (ADR 0003 §7). README with setup, architecture diagram, how to run eval.
Optional (only if G3 passed on time): src/credassure/mcp_server/ per design-detail §3.3 — read-only,
stdio, synthetic data only.
```
