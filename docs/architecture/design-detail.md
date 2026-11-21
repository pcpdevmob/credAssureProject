# CredAssure — Design detail (appendix to docs/architecture/ARCHITECTURE.md)

> Section numbers are referenced by docs/PHASE_PROMPTS.md. Repository layout (§1) is superseded by docs/REPO_STRUCTURE.md (ADR 0005); paths translate via the ADR 0005 path map. Where this file and ARCHITECTURE.md differ, ARCHITECTURE.md wins.

Implements `docs/BRD.md` v3.1. Where this file and the BRD disagree, the BRD wins; raise the conflict.

## 1. Project architecture

```
┌──────────────────────────── Streamlit UI (ui/) ─────────────────────────────┐
│ Login · Cases · Upload · Stage tracker · Funding · Offers · Copilot · Inbox │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ HTTPS + JWT (no direct agent calls — API-01)
┌───────────────────────────────▼─────────────────────────────────────────────┐
│ FastAPI (api/)  auth · RBAC · rate limit · request-id · upload validation   │
└───────┬───────────────────────┬──────────────────────────┬──────────────────┘
        │                       │                          │
┌───────▼────────┐   ┌──────────▼─────────┐     ┌──────────▼─────────┐
│ Supervisor     │   │ Copilot graph      │     │ Eval harness       │
│ LangGraph      │   │ classify→retrieve  │     │ (calls API)        │
│ (code gates)   │   │ →rerank→answer     │     └────────────────────┘
└───────┬────────┘   └──────────┬─────────┘
        │ invokes one agent per stage; agents never call each other
┌───────▼──────────────────────────────────────────────────────────────────────┐
│ Agents: Onboarding · WorkingCapital · LendWise · Critic · (Copilot)         │
│ each = bounded loop (≤10 steps) + allowlisted tools + versioned prompts     │
└───────┬──────────────────────────────────────────────────────────────────────┘
        │ tools (plain Python, typed, case_id injected by Supervisor)
┌───────▼──────────────────────────────────────────────────────────────────────┐
│ Engines (pure): cashflow · loancost(IRR/APR) · routing · normaliser ·       │
│ validators · onboarding_rules · affordability     Lender simulator         │
└───────┬──────────────────────────────────────────────────────────────────────┘
┌───────▼──────────┐ ┌───────────────┐ ┌───────────────┐ ┌────────────────────┐
│ case.db (SQLite) │ │ hr.db (RO)    │ │ corpus.db     │ │ Chroma (dense)     │
│ cases, ledger,   │ │ employees,    │ │ docs, chunks, │ │ chunk embeddings   │
│ audit (hash      │ │ trainings,    │ │ FTS5 BM25     │ │                    │
│ chain), approvals│ │ acks          │ │               │ │                    │
└──────────────────┘ └───────────────┘ └───────────────┘ └────────────────────┘
External: ≤8B chat endpoint · embeddings endpoint · Langfuse (self-hosted in Compose, ADR 0016)
```

### Repository layout

```
credassure/
├── .cursor/rules/                 # Cursor rules (this kit)
├── docs/ BRD.md ARCHITECTURE.md DATA_SPEC.md adr/ redteam_log.md
├── pyproject.toml  uv.lock  .env.example  Makefile  docker-compose.yml  Dockerfile
├── .pre-commit-config.yaml        # ruff, mypy, bandit, gitleaks
├── src/credassure/
│   ├── config.py                  # pydantic-settings; all thresholds & flags
│   ├── domain/
│   │   ├── money.py               # Decimal context, paise<->Decimal, Indian formatting
│   │   ├── enums.py               # Decision, Stage, Role, AgentName, FlagCode
│   │   ├── results.py             # AgentResult, Blocker, EvidenceRef  (FROZEN at G1)
│   │   └── schemas/               # case_files.py, offer.py, hr.py, kfs.py (versioned)
│   ├── engines/                   # PURE functions, no I/O
│   │   ├── cashflow.py            # weekly table, peak shortfall, recommendation, bridge
│   │   ├── loancost.py            # schedule, amount received, IRR, APR, total cost
│   │   ├── affordability.py       # overlay offer schedule on cash table (LW-09/10)
│   │   ├── ranking.py             # LW-11
│   │   ├── offer_audit.py         # LW-02/03/04
│   │   ├── onboarding_rules.py    # ONB-02/03
│   │   ├── routing.py             # APR-01..03
│   │   ├── normaliser.py          # ₹ / lakh / crore / % parsing (VER-01)
│   │   └── validators.py          # cross-file consistency (WC-02)
│   ├── ledger/ fact_ledger.py audit_log.py
│   ├── db/ models.py session.py migrations/ (alembic)
│   ├── llm/
│   │   ├── client.py              # OpenAI-compatible; cache, budget, retries, tracing
│   │   ├── structured.py          # parse → validate → repair ×2
│   │   ├── budget.py ratelimit.py cache.py
│   │   └── prompts/registry.py
│   ├── retrieval/ ingest.py chunking.py fts.py dense.py fusion.py rerank.py filters.py
│   ├── security/ pii.py spotlight.py injection.py authz.py
│   ├── tools/ registry.py         # 14 tools, typed signatures, per-agent allowlists
│   ├── lender_sim/ simulator.py scripts/*.yaml
│   ├── agents/
│   │   ├── supervisor/ graph.py state.py intent.py
│   │   ├── onboarding/  working_capital/  lendwise/  critic/  copilot/
│   ├── reports/ templates/*.j2 render.py
│   ├── observability/ tracing.py  # Langfuse with PII mask
│   ├── api/ main.py deps.py routers/{auth,cases,files,run,funding,offers,chat,decision,report,eval,health}.py
│   └── mcp_server/ server.py      # OPTIONAL dev tool, see §3.3
├── ui/ app.py pages/*.py api_client.py
├── data/
│   ├── generators/                # seeded generators (seed in config)
│   ├── frozen/v1/                 # generated, committed, frozen at G1
│   └── corpus/ manifest.yaml download.py   (raw files gitignored)
├── eval/
│   ├── testset/v1/items.jsonl     # 100 items, frozen
│   ├── retrieval/v1/queries.jsonl # 40 labelled queries
│   ├── gold/                      # independent gold computation (no engine imports)
│   ├── baseline/ s1_structured.py s2_cot_vote.py s3_decompose.py
│   ├── ablations.yaml             # A1–A5 flags + affected categories
│   ├── scorers.py harness.py report.py
└── tests/ unit/ property/ integration/ security/ conftest.py (FakeLLM)
```

## 2. Agent architecture

### 2.1 Shared contract (freeze at end of Week 1)

```python
class Decision(StrEnum):  GO="GO"; NO_GO="NO_GO"; NEEDS_INPUT="NEEDS_INPUT"; ERROR="ERROR"

class EvidenceRef(BaseModel):
    kind: Literal["ledger_fact", "passage", "hr_record", "offer_version", "file"]
    ref_id: str                     # ledger key / chunk_id / record id
    note: str | None = None

class Blocker(BaseModel):
    code: str                       # e.g. ONB_TRAINING_EXPIRED, WC_MISSING_FIELD, LW_NOT_AFFORDABLE
    message: str                    # plain language
    field: str | None = None
    next_action: str | None = None

class AgentResult(BaseModel):
    agent: AgentName; case_id: str; stage: Stage
    decision: Decision              # SET BY CODE ONLY
    evidence: list[EvidenceRef]; blockers: list[Blocker]
    question: str | None            # exactly one focused question when NEEDS_INPUT (SUP-06)
    output_ref: str | None          # pointer to stored artefact (cash table, ranking, draft)
    narrative: str | None           # model-drafted explanation; must pass Critic
    prompt_versions: dict[str, str]; steps_used: int; tokens_used: int; trace_id: str
```

### 2.2 Supervisor (master agent / planner) — LangGraph

`SupervisorState` (TypedDict): case_id, actor, stage_results{stage: AgentResult}, current_stage,
pending_question, route, budgets, return_to_stage, history.

Graph nodes and code-decided edges:

```
START → onboarding ─GO→ working_capital ─GO→ lendwise ─GO→ critic ─GO→ routing → await_approval(interrupt)
          │NO_GO/NEEDS_INPUT            │                 │               │critical finding
          └──────────► pause(question) ◄┴─────────────────┘               └──► reopen(offending stage)
await_approval: approve → END · reject → END · return(stage) → that stage
routing: amount == ₹1.5cr and rule=="hold" → hold_for_human
```

- Checkpointer: `langgraph.checkpoint.sqlite.SqliteSaver` on case.db → persistent state across turns,
  resume re-runs only the blocked stage (SUP-06).
- After any agent returns GO, the Supervisor **re-runs the deterministic checks** for that stage
  (SUP-05). Disagreement → override to NO_GO, audit `GATE_OVERRIDE`.
- Chat intent classifier (SUP-02): LLM picks one enum of
  {copilot_question, data_correction, approval_action, out_of_scope}; low-confidence or invalid → out_of_scope
  with clarification. Classification never triggers approval by itself; approval only via `/decision`.
- Track B mapping: planner = Supervisor (fixed plan + intent classifier), executors = stage agents,
  critic = Verification Critic. (Open mentor question Q1 — keep a flag `PLANNER_MODE=fixed|llm_proposes`
  where `llm_proposes` lets the model propose the next stage but code validates it against the fixed plan.)

### 2.3 Agents

| Agent | Model does | Code does (tools) | Gate rule (code) |
|---|---|---|---|
| Employee Onboarding | Explain failed rules in plain language; next steps | `get_hr_profile`, `evaluate_onboarding_rules` | GO iff all rules pass; any fail → NO_GO; missing record → NEEDS_INPUT |
| Working Capital Advisory | Map uploaded columns to schema if headers differ; explain drivers from ledger facts | `validate_case_files`, `compute_cash_table`, `compute_recommendation` | GO iff validation clean and recompute reproduces; else NEEDS_INPUT with one question |
| LendWise | Extract charges from KFS text into a fixed charge list (one offer per call); draft negotiation message from template slots | `audit_offer`, `price_offer`, `check_affordability`, `rank_offers`, `lender_send_template`, `reaudit_offer_version` | GO iff ≥2 comparable AND affordable offers (LW-14) |
| Verification Critic | Nothing in core (VER-06 stretch only) | `normalise_and_match_numbers`, `verify_citations`, `banned_content_scan`, `report_completeness` | GO iff zero critical findings; regenerate ×2 then template fallback |
| Ask CredAssure copilot | Classify question type; write cited answer from ≤5 passages; abstain | `search_knowledge` (FTS5+dense→RRF→rerank), `get_case_facts` | Answer only if Critic passes; else abstain string |

**Approval routing is code, not an agent:** `route_proposal` (engines/routing.py) is called by the Supervisor after Gate 4. **The copilot is on demand**, not a stage between the Critic and routing.

**The 14 tools** (registry, typed, each logs a span and audit event; `load_offers` added in 9c, ADR 0009): get_hr_profile,
evaluate_onboarding_rules, validate_case_files, compute_cash_table, compute_recommendation,
audit_offer, price_offer, check_affordability, rank_offers, lender_send_template,
search_knowledge, verify_claims (normaliser+citations+banned content), route_proposal,
load_offers (read-only: the case's latest offer and KFS uploads plus the funding position, LendWise only).

### 2.4 Per-agent detail

Every agent below has the same shape: inputs, a fixed pipeline, the LLM calls it is allowed (with prompt name), the ledger facts it writes, its blocker codes, the gate rule (code), and its test category. Step budget: 10 per invocation (SUP-07).

#### 2.4.1 Supervisor — master agent (owner: [Name 1])
- **Inputs:** case record, latest `AgentResult` per stage, `app_config`, chat message (for intent).
- **Pipeline:** load checkpoint → pick next stage from fixed plan (SUP-01) → check upstream gates GO + inputs validated (SUP-03) → invoke agent with `case_id` injected → validate `AgentResult` schema (repair ≤2, SUP-04) → on GO re-run that stage's deterministic checks (SUP-05) → advance / pause with one question (SUP-06) / reopen stage on Critic finding → after Critic GO call `route_proposal` → interrupt for approval.
- **LLM calls:** `sup_intent v1` only — enum {copilot_question, data_correction, approval_action, out_of_scope} (SUP-02). Never decides stage order or gates.
- **Writes:** `stage_runs`, audit events `STAGE_STARTED/COMPLETED/GATE_OVERRIDE/PAUSED/RESUMED/ROUTED`.
- **Blockers:** `SUP_UPSTREAM_NOT_GO`, `SUP_BUDGET_EXCEEDED`, `SUP_SCHEMA_INVALID`, `SUP_RECHECK_MISMATCH`, `SUP_ROUTE_HELD`.
- **Tests:** isolation 3/3, routing 6/6, end-to-end ≥4/5; forced-GO agent outputs still blocked.
- **As built (SUP-02, 2026-11-21):** chat intent is decided in code inside the copilot turn, after the refusal policy
  and the injection scan (`agents/copilot/intent.py::chat_action`): a data correction or an approval action gets a
  fixed reply naming the form or the Review & approval tab, and changes nothing; every other message is a copilot
  question (CP-07 routing), a refusal or an abstention. `sup_intent` (a model classifier) was never built. S18
  fixtures: 15/15 on intent, form and step.

#### 2.4.2 Employee Onboarding Agent — Gate 1 Readiness (owner: Tejas)
- **Inputs:** preparer `emp_id` from the authenticated user (never from chat — ONB-01); hr.db (read-only).
- **Pipeline:** `get_hr_profile(emp_id)` → `evaluate_onboarding_rules(profile, AS_OF_DATE)` returns per-rule {PASS, FAIL, UNKNOWN} for role, each mandatory training (status + expiry), policy ack version → code sets gate → LLM drafts the explanation of FAIL/UNKNOWN rules and next actions → Critic check that every failed rule is named.
- **LLM calls:** `onb_explain v1` (input: rule results table only, no raw HR record). Stretch ONB-07: `onb_checklist v1` with policy citations from `search_knowledge(collection=policy)`.
- **Writes:** ledger facts `onb.rule.<rule_id>` = PASS/FAIL/UNKNOWN with `source_ref=hr.db:<table>:<id>`.
- **Blockers:** `ONB_ROLE_NOT_AUTHORISED`, `ONB_TRAINING_EXPIRED`, `ONB_TRAINING_INCOMPLETE`, `ONB_TRAINING_MISSING` (→ NEEDS_INPUT), `ONB_ACK_MISSING`, `ONB_ACK_OLD_VERSION`.
- **Gate (code):** all PASS → GO; any FAIL → NO_GO; any UNKNOWN and no FAIL → NEEDS_INPUT. Re-runs when HR records change.
- **Safety:** no write tool to HR (ONB-05); PII redaction on chat (ONB-06).
- **Tests:** onboarding 10/10.

#### 2.4.3 Working Capital Advisory Agent — Gate 2 Funding Need (owner: Suresh)
- **Inputs:** case files (order, opening_position, costs, receipts, receivables, payables, inventory).
- **Pipeline:** optional header mapping (only when CSV headers differ) → `validate_case_files` (WC-01/02) → if blockers: pick highest-priority blocker by code → one question → NEEDS_INPUT; else `compute_cash_table` (26 weeks, confirmed receipts only, WC-05) → `compute_recommendation` (peak shortfall + buffer − undrawn limits − confirmed mitigations, round up to ₹1 lakh) → `bridge` from ₹2 cr request → write ledger → LLM drafts drivers explanation from ledger keys only (WC-07).
- **LLM calls:** `wc_header_map v1` (map unknown headers to a fixed field list; code validates); `wc_explain v1` (input: ledger facts dict).
- **Writes:** `wc.peak_shortfall`, `wc.peak_week`, `wc.shortfall_weeks`, `wc.min_buffer`, `wc.undrawn_limits`, `wc.mitigations`, `wc.recommended_amount`, `wc.bridge.<line>`, `wc.cash_table_ref`.
- **Blockers:** `WC_MISSING_FIELD`, `WC_CONFLICT_TOTALS`, `WC_DUPLICATE_ID`, `WC_UNIT_OR_CURRENCY`, `WC_DATE_OUT_OF_RANGE`, `WC_UNSOURCED_OFFSET`; warning `WC_MSE_PAYABLE_OVER_45D` (not a gate — RESOURCES D5).
- **Gate (code):** validation clean AND Supervisor recompute reproduces the recommendation exactly → GO.
- **Tests:** cash-flow 15/15 to ₹1; bridge sums exactly.

#### 2.4.4 LendWise Agent — Gate 3 Lender Comparison (owner: Pritish)
(Unchanged pipeline — see 2.4.7 for full step detail.)
- **Writes:** per offer `lw.<offer_id>.v<n>.{amount_received,total_repayment,total_cost,apr,flags,rank}`.
- **Blockers:** `LW_OFFER_INVALID`, `LW_MISSING_MATERIAL_TERM`, `LW_INSTALMENT_MISMATCH`, `LW_HIDDEN_CHARGE`, `LW_NOT_AFFORDABLE`, `LW_LATE_OR_SHORT`, `LW_RATE_MAY_RESET` (flag), `LW_BENCHMARK_NOT_EXTERNAL` (warning: MSE floating rate not linked to an external benchmark, RESOURCES D6), `LW_CGTMSE_INELIGIBLE` (warning: guarantee fee on a medium enterprise, D3), `LW_FEWER_THAN_TWO_ELIGIBLE`.
- **Gate (code):** ≥2 comparable AND affordable offers → GO.
- **Tests:** offers 15/15; negotiation safety 5/5.

#### 2.4.5 Verification Critic — Gate 4 Verification (owner: Abhishek)
- **Inputs:** any generated text (agent narratives, copilot answers, negotiation messages, report), the case ledger, cited chunk IDs.
- **Pipeline:** `verify_claims` = (a) normaliser extracts every amount/percent/date with span → match each to a ledger fact (₹1 / 0.01 pp; dates exact); (b) each citation: chunk exists, collection allowed, not superseded as of `AS_OF_DATE`, same case for KFS, quoted span/keywords present; (c) banned-content scan; (d) report completeness vs required sections → findings {critical, warning}.
- **On failure:** return findings to the owning stage; the owner regenerates (≤2) → then fixed template fallback (`reports/templates/fallback_*.j2`).
- **LLM calls:** none in core (by design the model does not check itself). Stretch VER-06 `ver_qual v1`.
- **Writes:** `critic_findings` (in `stage_runs.result_json`), audit `CRITIC_BLOCKED`, `CRITIC_FALLBACK`.
- **Blockers:** `VER_UNMATCHED_NUMBER`, `VER_BAD_CITATION`, `VER_SUPERSEDED_SOURCE`, `VER_BANNED_CONTENT`, `VER_PII`, `VER_REPORT_INCOMPLETE`.
- **Gate (code):** zero critical findings → GO.
- **Tests:** normaliser ≥50 formats; planted bad claims/citations blocked; fallback rate reported.

#### 2.4.6 Ask CredAssure Copilot — on demand, not a pipeline stage (owner: [Name 6])
- **Trigger:** `POST /cases/{id}/chat` when the Supervisor classifies the message as `copilot_question`. It can be used at any stage and never advances or blocks the workflow.
- **Pipeline:** PII redaction → refusal policy (code rules + `cp_refusal_classify v1`) → `cp_qtype v1` {regulatory, policy, case_fact, mixed} → `search_knowledge` (FTS5 + dense → RRF k=60 → rerank top-30→5, filters (ADR 0019): jurisdiction ∈ {IN, home state IN-MH}, applies_to ∈ {all, lender type}, effective ≤ AS_OF, not superseded, case_id for KFS) and/or `get_case_facts` → `cp_answer v1` with `[chunk_id]` citations from spotlighted passages, numbers only from case facts → Critic → answer or exact abstention string (CP-02).
- **Writes:** `chat_messages` (redacted), citations, trace_id.
- **Tests:** regulatory ≥20/25 with valid citation; refusal 8/8; injection 8/8; isolation 3/3; retrieval ≥34/40 in top 5.

- **As built (9e, 2026-11-16):** the refusal policy is code only (`agents/copilot/policy.py`), and
  `cp_tool` (a choice among the four fixed tools, scope #20) replaces `cp_qtype` and `cp_refusal_classify`.
  `cp_answer` cites `[n]`, which code maps to chunk ids. Case figures appear only as `{key}` slots.
  A case reads the corpus KFS it uploaded (doc_id + sha), exempt from `applies_to`. The Critic accepts
  a cited sentence's wording when the same word pair appears in the cited passage. With the model off,
  every non-refused question gets the abstention string. Memory keeps the last 4 redacted turns per
  user and case. Each answer is recorded as `cp.answer.<trace_id>`, with chunk ids, for lineage.
- **P5 (2026-11-18, plan v3.4 §7.1 CP-08-lite):** passages reach `cp_answer` 2.0.0 as numbered sentence
  spans `[n.m]` (code numbers them; bracketed ids in the source text are removed so none can be forged).
  The model ends every sentence with the span ids that support it; code cuts each sentence without a
  valid span id for that turn (or, on the case-facts path, a known slot), maps the rest to `[chunk_id]`,
  and the Critic then checks it. Nothing left gives the abstention string. Citations carry `span_ids`.
  Scoring is dual (ADR 0032 §4): strict (the frozen scorer) is the headline; supported = valid,
  current, allowed citations that judge J1 says support the answer, with a human sample.

- **P13 (2026-11-18, ADR 0035, product assistant):** the copilot also runs without a case (`POST /v1/copilot/chat`,
  `/stream`) on every page. Sources: product help (`docs/help`, ids `HELP-<page>#<slug>`, in-memory BM25), regulations,
  policies and, only inside a visible case, case figures (slots), status (`get_case_status`, code text) and blockers.
  Code routes the intent (CP-07, `intent.py`) after the refusal policy; `cp_tool` 1.1.0 is asked only when code is
  unsure, and a case tool without a case is invalid. Memory is the user's last 8 redacted messages in the case since
  their reset marker (CP-11). The stream sends stage events, then the Critic-passed text, then the reply (CP-12);
  follow-ups are a fixed list per intent; feedback is a fixed reason code from the answer's own recipient.

#### 2.4.7 LendWise step detail

Pipeline per case:
1. Load offers (versioned) → `audit_offer` (material-term checklist; instalment recompute vs stated EMI
   with ₹1 tolerance → `INSTALMENT_MISMATCH`).
2. Per offer, one LLM call: given spotlighted KFS text + the offer's declared charge list, output
   `KfsChargeExtraction{charges:[{name, basis: fixed|pct_of_principal|pct_of_outstanding, value_text, timing: upfront|monthly|annual, source_span}]}`.
   Code normalises `value_text` via normaliser; charges in KFS but not in offer → `HIDDEN_CHARGE` (LW-04).
   `source_span` must be a verbatim substring of the KFS — else discard that extraction (anti-hallucination).
3. `price_offer`: build borrower cash-flow vector incl. GST on all fees and CGTMSE fee (year 1 on guaranteed amount, then on outstanding — RESOURCES D2);
   IRR → APR; amount received; total repayment; total cost.
4. `check_affordability`: map instalment dates to weeks, add disbursal inflow at availability week,
   recompute cash table; min cash < buffer → `NOT_AFFORDABLE`; disbursal after peak week or amount <
   recommendation → `LATE_OR_SHORT` (LW-09/10).
5. `rank_offers`: comparable ∧ affordable; sort APR ↑, total cost ↑, availability ↑.
6. Negotiation round 1 (separate invocation): pick an offer whose fee > a verified competing fee;
   fill template `fee_waiver_v1` with ledger values only; Critic checks; simulator returns new version;
   re-audit + re-price; concession counts only after re-audit (LW-13, BR-09).
   *ADR 0037 (2026-11-19):* up to three rounds, one per invocation, in the fixed order `fee_waiver_v1` →
   `rate_match_v1` → `tenor_change_v1` (a move with no target is skipped); every counted concession is stored and the
   offers are re-ranked (`lw.ranking`, `lw.gate`), and `load_offers` merges stored revisions into the uploads.

### 2.5 Reconciliation with the team diagram (`docs/images/Flow_image.jpeg`)

The team's agent-centric diagram matches this design on users, UI → FastAPI → Supervisor, the deterministic tools row, fact ledger, RAG pipeline, Langfuse, deployment and error handling. Where it differs, **the BRD v3.1 wins** and the diagram should be updated:

| Diagram shows | BRD v3.1 / this kit | Action |
|---|---|---|
| Arrows chaining agent → agent | Agents never call each other; every hand-off goes through the Supervisor and the fact ledger (BRD §6) | Draw arrows agent ↔ Supervisor only |
| Ask CredAssure Copilot as a step between Critic and Approval | Copilot is on demand at any stage; not a gate | Move the copilot beside the pipeline, fed by chat |
| Approval Routing as an AI agent | Routing is code (`route_proposal`), no LLM (BR-12) | Show as a Supervisor node / tool |
| Document Processing "PDF/Word/CSV, OCR"; RAG "Parse / OCR"; Business Documents "(CSV/PDF)", bank statements | Case data JSON/CSV only; OCR, scans and images out of scope (BRD §4.3, Q-08); bank statements not in the data spec | Change to "JSON/CSV validation"; corpus parsing = text-layer PDF/HTML, no OCR |
| Onboarding "Verify identity" | Identity comes from login; agent checks role, training, policy ack (ONB-01..03) | Reword to "Check role" |
| Gate 5 Approval Routing | Stage 6 routing + Stage 7 human decision (BRD §7) | Label "Routing → Human decision" |
| Store "Chroma / FAISS" | Chroma (dense) + SQLite FTS5 (keyword) | Pick one; kit uses Chroma + FTS5 |
| Supervisor "calls subagents" (could read as LLM planner) | Code-driven fixed plan; LLM only classifies chat intent | Add "code decides gates" to the Supervisor box |

## 3. APIs and MCP

### 3.1 REST API (FastAPI, all JSON, JWT bearer)

| Method & path | Role | Purpose | Req |
|---|---|---|---|
| POST /auth/token | any | Login → JWT | NFR-07 |
| GET /health | any | Service + LLM endpoint + Langfuse status | — |
| POST /cases | preparer | Create case (indicative amount stored separately) | UI-01 |
| POST /cases/{id}/files?kind= | preparer | Upload JSON/CSV; field/row/reason errors | UI-02 |
| POST /cases/{id}/run | preparer | Start/resume (idempotency key header) | SUP-01, UI-09 |
| GET /cases/{id} | case members | Stage tracker state | UI-03 |
| GET /cases/{id}/funding | case members | Cash table, recommendation, bridge | UI-04 |
| GET /cases/{id}/offers | case members | Comparison, flags, negotiation history | UI-05 |
| POST /cases/{id}/chat | case members | Copilot / intent | UI-06, SUP-02 |
| GET /cases/{id}/inbox | routed approver | Pending decision | UI-07 |
| POST /cases/{id}/decision | routed approver | approve / reject / return{stage}, comment | APR-04/05 |
| GET /cases/{id}/report?fmt=md|html | case members | Report with trace IDs | UI-08 |
| GET /cases/{id}/audit | evaluator | Audit log (read-only) + hash-chain verify | OBJ-08 |
| POST /eval/runs | evaluator | Run test set / ablation (as built: 501, runs start with `make eval`; the gateway starts no process, ASI05) | — |
| GET /eval/runs/{id} | evaluator | Scores per category | — |
| POST /admin/config | evaluator | Boundary rule, buffers (audited) | APR-03 |

Errors: RFC 9457 problem+json. Every response carries `X-Request-ID` and, where relevant, `trace_id`.

### 3.2 Lender simulator interface

`LenderGateway` protocol with `send(case_id, lender_id, template_id, slots) -> OfferVersion`.
Core implementation is in-process and scripted from `lender_sim/scripts/*.yaml` (deterministic).
No real lender, bank, GST, ERP or bureau integration (BRD §4.3).

### 3.3 MCP — decision

**Runtime: no MCP.** Agents call tools in-process through `tools/registry.py`. Reasons: an 8B model
fumbles tool calls, MCP adds a transport/serialisation hop and a second auth surface, and the gates
must stay in code. Track B only requires ≥3 tools, not a protocol.

**Optional dev/demo add-on (stretch, after G3):** `src/credassure/mcp_server/server.py` using the
official `mcp` Python SDK (FastMCP), exposing **read-only** tools wrapping the same registry:
`search_knowledge`, `compute_cash_table`, `price_offer`, `route_proposal` (dry run). stdio transport only,
synthetic data only, no case writes, no approval. Useful for the team to probe engines from Cursor or
Claude Desktop and for a demo slide. Never on the runtime path.

## 4. Database

Three SQLite files + Chroma. SQLAlchemy 2 models, Alembic migrations, WAL mode, `PRAGMA foreign_keys=ON`.

**case.db**
- `users(id, username UNIQUE, role, password_hash, active)`
- `cases(id TEXT PK 'CA-YYYY-NNNN', msme_name, order_ref, order_value_paise, indicative_amount_paise, due_date, preparer_id FK, status, current_stage, route, created_at)`
- `case_files(id, case_id FK, kind, schema_version, sha256, payload_json, uploaded_by, created_at)` — newest version wins; old kept
- `stage_runs(id, case_id, stage, attempt, decision, result_json, trace_id, started_at, ended_at)`
- `ledger_facts(id, case_id, key, version, value_text, unit, source_type, source_ref, produced_by, input_hash, created_at, UNIQUE(case_id,key,version))`
- `offers(id, case_id, lender_id, offer_id, version, payload_json, kfs_doc_id, created_at, UNIQUE(case_id,offer_id,version))`
- `offer_evaluations(id, offer_row_id FK, comparable, affordable, amount_received_paise, total_repayment_paise, total_cost_paise, apr_text, flags_json, rank)`
- `negotiation_messages(id, case_id, offer_id, round, template_id, slots_json, rendered_text, critic_status, response_version, created_at)`
- `approvals(id, case_id, approver_id, role, decision, return_stage, comment, created_at)` — insert-only
- `audit_log(seq INTEGER PK, case_id, actor, event_type, payload_json, prev_hash, hash, ts)` — triggers
  `BEFORE UPDATE`/`BEFORE DELETE` → `RAISE(ABORT,'append-only')`; `hash = sha256(prev_hash || canonical_json)`
- `chat_messages(id, case_id, user_id, role, redacted_text, intent, citations_json, trace_id, created_at)`
- `prompt_registry(name, version, sha256, text, created_at)`; `app_config(key, value, updated_by, updated_at)`
- `eval_runs(id, config_json, started_at, finished_at)`; `eval_results(run_id, item_id, category, passed, score, failure_class, trace_id, tokens, latency_ms)`
- LangGraph checkpoint tables (created by SqliteSaver)

**hr.db** (opened `mode=ro` at runtime; written only by the generator)
- `employees(emp_id, display_name, role, department, status)`
- `required_trainings(role, course_id, validity_months)`
- `training_records(emp_id, course_id, status, completed_on, expires_on)`
- `policy_acknowledgements(emp_id, policy_id, policy_version, acknowledged_on)`

**corpus.db**
- `documents(doc_id, title, publisher, collection{public|policy|kfs|faq}, jurisdiction, effective_from, superseded_by, source_url, sha256, license_note, case_id NULL)`
- `chunks(chunk_id, doc_id, strategy{fixed512|section|semantic}, ordinal, text, section_path, injection_flag)`
- `chunks_fts` — FTS5 virtual table (`content='chunks'`, tokenizer `unicode61`), BM25 via `bm25(chunks_fts)`
- Chroma collection per chunking strategy, metadata mirrors filter fields (KR-04)

## 5. Security guardrails summary
See `.cursor/rules/10-security-guardrails.mdc`. Threat model in `docs/adr/0002-threat-model.md`
(STRIDE over UI, API, agents, documents, LLM endpoint). Red-team log of 20 prompts in `docs/redteam_log.md`.

## 6. Observability
One Langfuse trace per case run and per eval item; spans per agent step, tool call, retry, Critic finding.
Mask function = `security.pii.redact`. Metrics recorded: tool calls/task, tokens/stage, latency, Critic
fallback rate, failure class {retrieval_miss, reasoning_error, tool_error, hallucination}.

## 7. Additions from the build scope (docs/BUILD_SCOPE.md)

| Addition | Where | Scope # |
|---|---|---|
| `Plan` object per case, logged as a span; `PLANNER_MODE=fixed\|llm_proposes` (code validates) | `agents/supervisor/plan.py` | #19 |
| Copilot chooses among 4 fixed tools; code validates and executes | `agents/copilot/tool_choice.py` | #20 |
| `CriticFinding` → `regenerate v1` prompt per agent | `domain/findings.py` | #21 |
| WAL, busy_timeout, one active run per case, shared rate limiter, parallel per-offer calls | `db/session.py`, `llm/ratelimit.py` | #22 |
| 30 s model-call and 5 min stage timeouts with cancellation | `llm/client.py`, Supervisor | #23 |
| Agent registry + data-access matrix enforced in tool layer | `agents/registry.yaml`, `tools/registry.py` | #24 |
| `agent_version` in AgentResult; `POST /v1/cases/{id}/stages/{stage}/retry` | `domain/results.py`, API | #25 |
| `tenant_id` on case tables; `/v1` routes; error catalogue | `db/models.py`, `api/`, `domain/errors.py` | #27, #28, #32 |
| `GET /v1/cases/{id}/facts/{key}/lineage`; `DELETE /v1/cases/{id}` (audit tombstone) | API | #33, #39 |
| Copilot conversation memory (per case, redacted) | `agents/copilot/memory.py` | #2 |
| Structured JSON logging | `observability/logging.py` | #31 |
| Corpus legal-basis audit | `data/corpus/audit.py` | #14 |

All REST paths in §3.1 are served under `/v1`.
