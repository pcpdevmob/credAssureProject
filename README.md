# CredAssure

**Agentic MSME working-capital loan proposal workflow**, built for the IIT Kharagpur Executive PG Programme in Generative AI and Agentic AI (Capstone **Track B**: an API-side multi-agent system on a hosted ≤8B model, no fine-tuning, synthetic data only).

> **The design rule:** the model reads, explains and drafts. Code calculates, routes and gates. A human approves.

CredAssure (formerly *FinBridge AI*) takes an MSME working-capital case through four gated stages:
1. **Onboarding:** confirms from HR records that the preparer is trained and authorised.
2. **Working Capital:** sizes the funding need from a 26-week cash-flow forecast (not from the ₹2 crore request).
3. **LendWise:** audits lender offers against their Key Facts Statement (KFS), prices them by APR, checks affordability and ranks them.
4. **Critic:** verifies every number and citation against the fact ledger.

Code then routes the proposal: above ₹1.5 crore to the VP, Finance; below to the Director, Finance; exactly ₹1.5 crore is **held** by default. The model never decides a gate, never computes a figure, and never accepts, signs or submits a lender offer.

Requirements: [docs/requirements/BRD.md](docs/requirements/BRD.md) · Architecture: [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) · Progress: [PROGRESS.md](PROGRESS.md)

---

## Contents
1. [Agents and owners](#1-agents-and-owners)
2. [Prerequisites](#2-prerequisites)
3. [Configure `.env`](#3-configure-env)
4. [Install](#4-install)
5. [Model: local Ollama or the course API](#5-model-local-ollama-or-the-course-api)
6. [Data: databases, corpus, demo cases](#6-data-databases-corpus-demo-cases)
7. [Run the app](#7-run-the-app)
8. [Tests and quality checks](#8-tests-and-quality-checks)
9. [Evaluation](#9-evaluation)
10. [Working with Claude Code](#10-working-with-claude-code)
11. [Troubleshooting](#11-troubleshooting)
12. [Repository layout](#12-repository-layout)
13. [Status, data and licences](#13-status-data-and-licences)

**Quick start** (after §2–§3):
```bash
make install && npm install
make data && make db && make ingest
OLLAMA_CONTEXT_LENGTH=8192 ollama serve      # terminal 1
make run-api                                 # terminal 2 → http://localhost:8000/docs
make run-ui                                  # terminal 3 → http://localhost:3000
```

---

## 1. Agents and owners

| Agent | Package | Job | Owner |
|---|---|---|---|
| Supervisor and routing | `agents/supervisor` | Fixed stage order, code gates, re-check of every GO, pause and resume, approval wait, routing by amount | [Name 1] |
| Employee Onboarding | `agents/onboarding` | Role, required trainings and policy acknowledgement from the read-only HR store | Tejas |
| Working Capital | `agents/working-capital` | 26-week cash table, peak shortfall, buffer, recommended amount and bridge | Suresh |
| LendWise | `agents/lendwise` | KFS hidden-charge audit, APR by IRR (GST, insurance, CGTMSE), affordability, ranking, one fee-waiver negotiation draft | Pritish |
| Verification Critic | `agents/critic` | Number normaliser vs ledger, citation checks, banned content, regenerate ×2 then template fallback | Abhishek |
| Ask CredAssure Copilot | `agents/copilot` | On-demand hybrid RAG over 1,084 real Indian documents, cited answers, refusals | [Name 6] |

Shared code: `packages/core` (contracts, `AgentResult` per ADR 0018, ports, errors, prompt registry), `packages/engines` (deterministic money, APR, cash flow, routing), `packages/ledger` (models, migrations, fact ledger, hash-chained audit), `packages/llm`, `packages/retrieval`, `packages/security`, `packages/tools`, `packages/lender-sim`, `packages/reports`, `packages/observability`, `apps/gateway` (FastAPI), `apps/web` (Next.js/React), `packages/api-client` (generated TypeScript client).

---

## 2. Prerequisites

| Tool | Version | Install (macOS) | Notes |
|---|---|---|---|
| git | any recent | Xcode CLT | |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | Manages Python and the workspace |
| Python | 3.12 | `uv python install 3.12` | Don't use the system Python |
| Node.js + **npm** | Node 20 LTS | `brew install node@20` or nvm | The Makefile uses npm workspaces. Don't use yarn, and don't run `corepack enable` |
| Ollama | latest | https://ollama.com/download | Local model (default) |
| Docker + Compose | optional | Docker Desktop | Langfuse tracing and the containerised stack |
| make, openssl, sqlite3 | system | preinstalled on macOS | |

Hardware: a 16 GB Apple Silicon Mac runs `qwen3:8b` fully on the GPU at an 8K context.

| Port | Service |
|---|---|
| 8000 | Gateway API (`make run-api`), Swagger at `/docs` |
| 3000 | Web app (`make run-ui`) **and** Langfuse (Compose). They clash; see §11 |
| 5173 | Web container (`make up`), or the UI's second dev port |
| 11434 | Ollama |
| 8001 / 3001 | Isolated e2e API / web |

---

## 3. Configure `.env`

```bash
cp .env.example .env
# JWT_SECRET signs login tokens; the API refuses to start without it (32+ chars).
sed -i '' '/^JWT_SECRET=$/d' .env          # Linux: sed -i '/^JWT_SECRET=$/d' .env
printf 'JWT_SECRET=%s\n' "$(openssl rand -hex 32)" >> .env
```

Then edit `.env` by hand:

| Key | When | Value |
|---|---|---|
| `SEED_PASSWORD` | always | 12+ characters; password for every seeded user (`SEED_PASSWORD_<USERNAME>` overrides one) |
| `LLM_ENABLED` | optional | `false` runs everything without a model (template narratives) |
| `CORPUS_CONTACT_EMAIL` / `CORPUS_CONTACT_URL` | optional | Added to the harvester's User-Agent so a site admin can reach you rather than block you |
| `LLM_API_KEY`, `EVAL_API_KEY`, `EMBED_API_KEY` | course only | From the course portal |
| `LLM_CA_CERT`, `EMBED_CA_CERT` | course only | Absolute paths, e.g. `~/.credassure/certs/vm06-ca.crt`, `vm02-ca.crt` |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | with tracing | From your self-hosted Langfuse project (§7) |

Rules:
- **Never commit `.env`**, never paste it into a chat, and never ask Claude Code to read it (a hook blocks it).
- Keep certificates **outside the repo** (`mkdir -p ~/.credassure/certs && chmod 700 ~/.credassure`).
- Don't put `MODELS` or `E2E_*` in `.env`. `MODELS` is a make variable (§5), and the e2e targets set their own URLs (§8).

---

## 4. Install

```bash
make install     # uv sync --all-packages: every workspace member + dev group
npm install      # npm workspaces: apps/web and packages/api-client
uv run pre-commit install   # optional: ruff, mypy, bandit, gitleaks on commit
```

> **Never run a bare `uv sync`.** It removes workspace members that aren't root dependencies, and imports then break (`ModuleNotFoundError: credassure.agents…`).

---

## 5. Model: local Ollama or the course API

The Makefile loads `.env` first and then `deploy/env/models-$(MODELS).env`, so the profile **overrides** every model setting. Keys and cert paths stay in `.env`.

| | `MODELS=local` (default) | `MODELS=course` (graded) |
|---|---|---|
| Chat model | `qwen3:8b` via Ollama `http://localhost:11434/v1` | `Qwen/Qwen3-8B` on the course endpoint |
| Thinking off | `reasoning_effort` | `chat_template_kwargs` (confirm with `make llm-probe`) |
| Embeddings | in-process `bge-small` (`EMBED_BASE_URL=local`) | course `bge-small-en-v1.5` endpoint |
| Chroma index | `var/chroma-local-bge` | `var/chroma-course-bge` |
| Rate limit | 600/min | 55/min |

The `/no_think` prompt tag is ignored by Ollama. Turning thinking off keeps explanations at 1.5–4 s instead of 17–65 s.

### Local (Ollama)
```bash
OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_KEEP_ALIVE=30m ollama serve   # leave this terminal open
make ollama-pull                                                # qwen3:8b (+ nomic-embed-text), ~5 GB, once
ollama run qwen3:8b --think=false "Reply with OK" --verbose
ollama ps          # expect CONTEXT 8192 and PROCESSOR 100% GPU
```

If you'd rather run the Ollama menu-bar app, set the variables for launchd once, then quit and reopen the app:
```bash
launchctl setenv OLLAMA_CONTEXT_LENGTH 8192
launchctl setenv OLLAMA_KEEP_ALIVE 30m
```

### Course endpoint
```bash
# put the course keys and cert paths in .env first (§3)
make llm-probe       MODELS=course   # reachability, context, guided-JSON support
make ingest          MODELS=course   # once: builds the course embeddings index
make retrieval-eval  MODELS=course
make baseline        MODELS=course   # graded S1–S3 prompting baseline (G1 evidence)
make run-api         MODELS=course
```
Add `MODELS=course` to **every** target that touches the model. Only set `LLM_SUPPORTS_GUIDED_JSON=true` after `llm-probe` confirms it.

### No model
`LLM_ENABLED=false make run-api` still runs every gate, calculation, routing and approval. Narratives fall back to templates and the copilot answers "unavailable". The demo must work in this mode too.

---

## 6. Data: databases, corpus, demo cases

```bash
make data         # seeded synthetic data -> data/frozen/v1 + hr.db (idempotent; frozen files are hook-protected)
make db           # migrate var/case.db + var/corpus.db, seed users into tenant "demo"
make ingest       # chunk + embed the corpus into var/corpus.db (FTS5) + Chroma; re-runnable
make demo-reset   # rebuild the demo cases. STOP `make run-api` FIRST
```

`make demo-reset` backs up `var/case.db`, purges the demo tenant's cases (audited) and recreates **10 demo cases through the real API**. It is idempotent: the same IDs and states every run. None is approved, so you can show an approval live.

| Source case | MSME | State | Shows |
|---|---|---|---|
| CA-2026-0001 | Demo Electronics | Awaiting approval → Director | Main demo: 2 of 3 offers eligible, unaffordable lender dropped |
| CA-2026-0003 | Demo Circuits | Awaiting approval → Director | Floating-rate flag, hidden charge caught |
| CA-2026-0006 | Demo Assemblies | Awaiting approval → VP | Need above ₹1.5 crore |
| CA-2026-0007 | Demo Sensors | Awaiting approval → VP | Confirmed mitigation |
| CA-2026-0008 | Demo Mid-Size | Awaiting approval → VP | Medium enterprise: CGTMSE offer flagged ineligible |
| CA-2026-0010 | Demo Boundary | **Held** | Exactly ₹1.5 crore, boundary rule |
| CA-2026-0004 | Demo Fees | Paused (LendWise) | Only 1 eligible offer |
| CA-2026-0005 | Demo Rejects | Paused (LendWise) | Missing term, instalment mismatch, unaffordable |
| CA-2026-0013 | Demo Paused Case | Paused (Working Capital) | No `min_cash_buffer`: one question to the preparer |
| CA-2026-0014 | Demo Conflict | Paused (Working Capital) | Conflicting receipts, duplicate invoice ID |

The new cases get fresh IDs; the table names the frozen case each one copies. Run `make demo-reset` before every rehearsal.

### Corpus
1,084 real Indian documents (target ≥500 met) plus synthetic policies and KFS documents, 1,275 indexed in total. Sources: RBI, CGTMSE, e-Gazette, CBIC, India Code, Udyam, MSME Samadhaan, SIDBI, data.gov.in and bank charge schedules. Full list: [docs/data/DATA_RESOURCES.md](docs/data/DATA_RESOURCES.md) and `data/corpus/CORPUS_INDEX.md` / `.xlsx`.

```bash
make corpus-status    # real / available / manual-pending per source and owner
make corpus-harvest   # polite harvester: robots.txt, 1 request/s, stops on 403/429/challenge
make corpus-import    # import files saved by hand into data/corpus/raw/
make corpus-verify    # SHA-256 check against data/corpus/manifest.lock.json
make corpus-audit     # legal-basis audit of the manifest
```

Corpus rules (non-negotiable):
- Respect robots.txt; at most one request per second; **stop that host on any block**.
- No spoofed headers, headless browsers, CAPTCHA solving or bot-block bypass.
- RBI, e-Gazette, incometaxindia and India Code are **downloaded by hand** (`data/corpus/MANUAL_DOWNLOADS.md`), then `make corpus-import`.
- Harvest from a personal machine and network, not an employer network.
- **Never commit raw L3/L4 files.** `data/corpus/raw/` and `text/` are git-ignored; only the manifest, lock file and metadata are committed.

---

## 7. Run the app

**Terminal 1: Ollama** (§5, skip with `LLM_ENABLED=false`)

**Terminal 2: API**
```bash
make run-api                              # http://localhost:8000 (tenant "demo", var/case.db)
curl -s localhost:8000/v1/health/live     # {"status":"ok"}
curl -s localhost:8000/v1/health/ready    # databases, model circuit, quota
open http://localhost:8000/docs           # Swagger
```

**Terminal 3: Web UI**
```bash
make run-ui                               # Next.js on http://localhost:3000
```

Sign in with your `SEED_PASSWORD`:

| Username | Role | Can do |
|---|---|---|
| `demo.preparer`, `demo.preparer2`, `prep.e001` … `prep.e020` | Preparer | Create a case, upload files, run stages, answer pauses, ask the copilot |
| `demo.director` | Director, Finance | Approve, reject or return proposals **below** ₹1.5 crore |
| `demo.vp` | VP, Finance | Approve, reject or return proposals **above** ₹1.5 crore and held boundary cases |
| `demo.evaluator` | Evaluator | Run evaluations, read traces and the audit log, retry a stage |

Maker-checker: whoever prepares a case can't approve it. `prep.e0xx` users map to the 20 HR profiles, so some fail onboarding by design (expired training, wrong role and so on).

### Tracing (Langfuse, self-hosted)
```bash
cp deploy/env/langfuse.env.example deploy/env/langfuse.env   # replace every CHANGEME
make langfuse-up             # UI on http://localhost:3000; create a project, put its keys in .env
make langfuse-down
```
Langfuse takes :3000, so run the web UI on 5173 meanwhile (§11). `TRACING_ENABLED=false` turns tracing off.

### Everything in Docker
```bash
make up                      # gateway :8000, web :5173, Ollama, Langfuse (dev profile)
make down
make compose-test            # gateway with the LLM off, no tracing
make compose-demo            # gateway in demo mode + Langfuse
make ollama-pull             # pulls into the Ollama container when it is running
```

---

## 8. Tests and quality checks

```bash
make check-fast    # ruff + tests not marked slow (the Claude stop hook runs this)
make check         # ruff, ruff format, mypy --strict, pytest, corpus refs, bandit, import-linter. Must be green before commit
make test          # full suite with coverage
make audit         # pip-audit (accepted advisories: docs/security/risk-register.md)
```

Web:
```bash
npm run typecheck -w apps/web
npm run test -w apps/web          # vitest
npm run build -w apps/web
```

**End-to-end (isolated, never touches `var/case.db`):**
```bash
make e2e-db         # fresh var/case-e2e.db (refuses the demo database)
make run-api-e2e    # API on :8001
make run-ui-e2e     # UI on :3001 → :8001
make e2e            # Playwright; PW_ARGS="--project=u3" for one project
```

**API contract → TypeScript client**, after any API schema change:
```bash
make openapi && make client       # regenerates openapi.json and packages/api-client
```

---

## 9. Evaluation

| Command | What it does |
|---|---|
| `make retrieval-eval` | recall@5/@10 for 40 queries, 3 retrievers × 3 chunkers × rerank. Fails only on a KR-04 violation or a cross-case KFS leak |
| `make retrieval-pool` / `make retrieval-silver` | Blind pooled top-5 for judging; silver labels (v1.1-silver) |
| `make judge JUDGE=<name>` | Human judging of the 249-item sample, resumable (each judge uses their own name) |
| `make kappa JUDGE=<name>` | Plain and weighted κ, human vs silver. Target: weighted κ ≥ 0.7 |
| `make baseline` | Prompting strategies S1–S3 on the frozen 100-item test set |
| `make copilot-live` | The 44 copilot items through the API on the configured model |
| `make eval-fast` | Prompt change control: version-bump check + offline prompt subset |
| `make eval` | Full 100-item harness (Phase 11, not yet implemented) |
| `/eval E1 … E18` | Claude Code evaluation reports, saved to `evaluation/reports/` |
| `/freeze-g1` | Writes `evaluation/FROZEN.sha256`, **only after** the human checks are done |

Frozen artefacts: the 100-item test set (25/10/15/15/5/6/8/8/3/5 by BRD §13 category), 40 retrieval queries (v1.0 + v1.1-silver), 20 red-team prompts, bad-citation fixtures, the RBI KFS APR illustration, and `data/frozen/v1`.

Current numbers (local `qwen3:8b`):
- Onboarding **10/10**, cash flow **15/15**, LendWise offers **15/15**, negotiation **5/5**.
- Copilot safety: refusal **8/8**, injection **8/8**, isolation **3/3**.
- Retrieval recall@5: v1.0 **24/40**; silver strict **35/40**.
- Copilot regulatory: **10/25**, limited by retrieval.

The silver figure is high partly because silver labels and the retriever share signals; the human κ check measures that.

---

## 10. Working with Claude Code, Cursor or other AI tools

**Taking over or continuing a module?** Follow [docs/setup/team-handoff.md](docs/setup/team-handoff.md). It covers where the context lives, the handoff steps, a kickoff prompt for any tool, the guardrail checklist and the module map.

| Tool | Loads automatically | Guardrails |
|---|---|---|
| Claude Code | [CLAUDE.md](CLAUDE.md) (+ the docs and rules it imports), `.claude/` | Enforced by hooks |
| Cursor | `.cursor/rules/*.mdc`, [AGENTS.md](AGENTS.md) | Manual checklist (handoff §4) |
| Codex, Copilot, Windsurf, Gemini… | [AGENTS.md](AGENTS.md) | Manual checklist (handoff §4) |

Open Claude Code in the repo root; it loads `CLAUDE.md` automatically.

- **Build prompts:** `prompts/00–26` (phases), `CLAUDE_CODE_UI_PROMPT.md` (UI U0–U6), [docs/build/PHASE_PROMPTS.md](docs/build/PHASE_PROMPTS.md). One phase per session; stop at its gate.
- **Commands:** `/status`, `/next`, `/phase <n>`, `/gate <G>`, `/eval <E#>`, `/review`, `/ui U<n>`, `/freeze-g1`.
- **Progress:** `PROGRESS.md` is the single source of truth for done, open and deferred work.
- **Subagents** (`.claude/agents/`): `brd-conformance`, `security-reviewer`, `money-auditor`, `test-writer`, `eval-analyst`.
- **Hooks** (`.claude/hooks/`): `guard_paths.py` (blocks `.env`, certificates, raw corpus, frozen sets), `guard_bash.py` (blocks `git push`, recursive force delete, printing `.env`), `format_python.py`, `check_before_stop.py` (runs `make check-fast`).

Working rules:
- **Claude never pushes.** You review the diff and push yourself.
- Never paste secrets or passwords into a prompt.
- Synthetic data only: no real customer, PAN, Aadhaar or account data, ever.
- No code path may accept, sign or submit a lender offer. Negotiation produces drafts for a human.
- A change to a frozen artefact needs a new version (v2) and an ADR, never an in-place edit.
- Commit messages carry requirement IDs, e.g. `phase-9c-b: lendwise negotiation [LW-12, LW-13]`.

---

## 11. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| API exits on startup | `JWT_SECRET` missing or < 32 chars, or `LLM_BASE_URL` unset with `LLM_ENABLED=true` | §3 `printf` command |
| `ModuleNotFoundError: credassure.agents…` | A bare `uv sync` removed workspace members | `make install` |
| Web app and Langfuse both want :3000 | Same port | `npm run dev -w apps/web -- -p 5173` (5173 is in the default `UI_ORIGINS`) |
| Sign-in fails with a CORS error | UI on a port the API doesn't allow | Use :3000 or :5173, or add the origin to `UI_ORIGINS` |
| UI calls fail with 401 after a restart | Token signed with an old `JWT_SECRET` | Sign out and in again |
| UI type errors after an API change | Client out of date | `make openapi && make client` |
| Explanations take 17–65 s | Qwen3 thinking is on | Run with `MODELS=local` (the default); restart the API |
| `ollama ps` shows a 4096 context | Server started without the variable | `OLLAMA_CONTEXT_LENGTH=8192` (§5) |
| `bind: address already in use :11434` | App and CLI both running | `killall Ollama; pkill -f "ollama serve"; pkill -f "ollama runner"`, then `lsof -i :11434` should print nothing |
| `make demo-reset` refuses or says "database locked" | API still running on :8000 | Stop `make run-api` first |
| Demo cases show e2e leftovers | e2e ran against the demo DB, or stale state | Stop the API → `make demo-reset` → restart |
| Copilot always answers "I can't verify that…" | Model off, or no index for the current `MODELS` | Start Ollama / run `make ingest` with the same `MODELS` |
| `make llm-probe` says variables missing | Course values not in `.env` | Add them (§3) |
| `make corpus-import` rejects a PDF | Scanned PDF, no text layer | Use the replacement in `MANUAL_DOWNLOADS.md` |
| Harvester stops on a host | 403/429/challenge page | Expected: download those by hand. Don't work around it |
| `/offers` shows an old comparison | Offers re-uploaded, stage not re-run | Re-run the LendWise stage (staleness handling is Phase 10) |

---

## 12. Repository layout

```
CredAssure/
├── agents/                 # one uv project per agent: src/ (agent, tools, prompts/*.yaml, api/ router) + tests/
│   ├── supervisor/  onboarding/  working-capital/  lendwise/  critic/  copilot/  registry.yaml
├── packages/
│   ├── core/  engines/  ledger/  llm/  retrieval/  security/
│   ├── tools/  lender-sim/  reports/  observability/
│   └── api-client/         # generated TypeScript client (npm workspace)
├── apps/
│   ├── gateway/            # FastAPI /v1, auth, jobs + SSE, RFC 9457 errors, seed
│   └── web/                # Next.js/React UI (npm workspace)
├── data/
│   ├── generators/         # seeded synthetic data
│   ├── reference/          # AGF slabs, GST, reference rates
│   ├── frozen/v1/          # synthetic cases, HR store, offers, KFS, users (frozen)
│   └── corpus/             # manifest.yaml, manifest.lock.json, MANUAL_DOWNLOADS.md (raw/ git-ignored)
├── evaluation/             # testset, retrieval, gold, judging, redteam, baseline, reports
├── var/                    # local databases, Chroma, caches, backups (git-ignored)
├── scripts/                # demo_reset.py, e2e_guard.py, copilot_live.py
├── prompts/                # Claude Code build prompts 00–26 (agent prompts live in agents/*/prompts/)
├── deploy/                 # env profiles, Dockerfiles, compose, nginx, backup/restore scripts
├── docs/                   # requirements, architecture, adr, data, setup, security, ui, build
├── .claude/  .cursor/  .github/
└── CLAUDE.md  PROGRESS.md  Makefile  pyproject.toml  package.json  openapi.json
```

---

## 13. Status, data and licences

**Gates**
- **G1:** provisionally frozen. Final after human judging and κ, the gold hand check, the APR second transcription, remaining owner names and the course baseline.
- **G2:** passed (2026-11-15).
- **G3, G4:** pending.

**Done:** Phases 1–9e (Copilot CP-01 open on retrieval quality) and UI U1–U3.

**Next:** UI U4 and the demo pack, Phase 10 and G3, the course-endpoint switch, Phase 11, U5–U6, Phase 12, G4, the report.

**Data**
- All case, HR, offer and KFS data is **synthetic**.
- The corpus is public Indian material only (ADR 0019), under these legal bases:
  - **L1:** GODL-India.
  - **L2:** Gazette matter and judgments, Copyright Act s.52(1)(q).
  - **L3:** Acts. Store locally, quote short passages, never commit.
  - **L4:** public documents and facts, for research use. Never redistributed.
  - **L5:** team-owned.

**Licences**
- Code: **MIT**.
- Synthetic data, evaluation sets and documentation: **CC BY 4.0**.
- Third-party documents keep their own terms and are not redistributed in this repo.

### Feature flags
Validated at startup by `apps/gateway/src/credassure/gateway/settings.py`; defaults are fail-safe. Every setting is in
[docs/setup/environment.md](docs/setup/environment.md) and `.env.example` (kept in sync by `test_settings.py`).

| Variable | Default | Values | Effect |
|---|---|---|---|
| `APP_ENV` | `dev` | dev, test, demo | `test` relaxes the required-secret checks only |
| `LLM_ENABLED` | `true` | bool | `false` = template fallbacks; `LLM_BASE_URL` then not required |
| `TRACING_ENABLED` | `true` | bool | Langfuse tracing on/off (PII mask always applies) |
| `RERANKER` | `none` | none, local_cross_encoder, llm_pointwise | ADR 0013 |
| `APR_CONVENTION` | `nominal` | nominal, effective | ADR 0012 |
| `BOUNDARY_RULE` | `hold` | hold, director, vp | Exactly ₹1.5 crore routing (APR-03) |
| `APPROVAL_STEP_UP` | `true` | bool | Approving above ₹1.5 crore asks for the password again (NFR-07) |
| `PLANNER_MODE` | `fixed` | fixed, llm_proposes | Scope #19; code validates any proposal |
| `COPILOT_SEARCH_MODE` | `hybrid` | hybrid, keyword | Copilot retrieval |
| `FEATURE_STRETCH` | `false` | bool | BRD §4.2 stretch items |
| `ABLATION` | empty | A1..A5 | Evaluation only (BRD §12) |

> **Not financial or legal advice.** CredAssure is an academic prototype. Every proposal requires human approval, and the system never commits a business to a lender.
