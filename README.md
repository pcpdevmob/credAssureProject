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

Responsible AI and security: [System card](docs/SYSTEM_CARD.md) · [Threat model](docs/THREAT_MODEL.md) · [OWASP LLM + ASI mapping](docs/security/owasp-asi-mapping.md) · Operations: [Runbook](docs/deployment/RUNBOOK.md) · [Hosted deployment](docs/deployment/azure.md) · Team: [CONTRIBUTIONS.md](CONTRIBUTIONS.md) · Changes: [CHANGELOG.md](CHANGELOG.md)

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
10. [Working with the coding tool](#10-working-with-the-coding-tool-cursor-or-other-ai-tools)
11. [Team workflow: branches, PRs and progress](#11-team-workflow-branches-prs-and-progress)
12. [Troubleshooting](#12-troubleshooting)
13. [Repository layout](#13-repository-layout)
14. [Status, data and licences](#14-status-data-and-licences)

**Quick start** (after §2–§3):
```bash
make install && npm ci
make hr-db && make db && make ingest          # data/frozen/v1 is committed (frozen); hr-db rebuilds hr.db
OLLAMA_CONTEXT_LENGTH=8192 ollama serve      # terminal 1
make run-api                                 # terminal 2 → http://localhost:8000/docs
make run-ui                                  # terminal 3 → http://localhost:3000
```

---

## 1. Agents and owners

| Agent | Package | Job | Owner |
|---|---|---|---|
| Supervisor and routing | `agents/supervisor` | Fixed stage order, code gates, re-check of every GO, pause and resume, approval wait, routing by amount | Abhishek |
| Employee Onboarding | `agents/onboarding` | Role, required trainings and policy acknowledgement from the read-only HR store | Mousita (0.3.0; Tejas built 0.1–0.2) |
| Working Capital | `agents/working-capital` | 26-week cash table, peak shortfall, buffer, recommended amount and bridge | Suresh |
| LendWise | `agents/lendwise` | KFS hidden-charge audit, APR by IRR (GST, insurance, CGTMSE), affordability, ranking, one fee-waiver negotiation draft | Pritish |
| Verification Critic | `agents/critic` | Number normaliser vs ledger, citation checks, banned content, regenerate ×2 then template fallback | Abhishek |
| Ask CredAssure Copilot | `agents/copilot` | On-demand hybrid RAG over 1,084 real Indian documents, cited answers, refusals | Adesh (retrieval: Adesh, Tejas; corpus: Tejas, Pritish) |

Shared code: `packages/core` (contracts, `AgentResult` per ADR 0018, ports, errors, prompt registry), `packages/engines` (deterministic money, APR, cash flow, routing), `packages/ledger` (models, migrations, fact ledger, hash-chained audit), `packages/llm`, `packages/retrieval`, `packages/security`, `packages/tools`, `packages/lender-sim`, `packages/reports`, `packages/observability`, `apps/gateway` (FastAPI), `apps/web` (Next.js/React), `packages/api-client` (generated TypeScript client).

---

## 2. Prerequisites

| Tool | Version | Install (macOS) | Notes |
|---|---|---|---|
| git | any recent | Xcode CLT | |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | Manages Python and the workspace |
| Python | 3.12 | `uv python install 3.12` | Don't use the system Python |
| Node.js + **npm** | Node 22 LTS (≥ 22.12; vitest 5 needs it) | `brew install node@22` or nvm | The Makefile uses npm workspaces. Don't use yarn, and don't run `corepack enable` |
| Ollama | latest | https://ollama.com/download | Local model (default) |
| Docker + Compose | optional | Docker Desktop | Langfuse tracing and the containerised stack |
| make, openssl, sqlite3 | system | preinstalled on macOS | |

Hardware: a 16 GB Apple Silicon Mac runs `qwen3:8b` fully on the GPU at an 8K context.

| Port | Service |
|---|---|
| 8000 | Gateway API (`make run-api`), Swagger at `/docs` |
| 3000 | Web app (`make run-ui`) **and** Langfuse (Compose). They clash; see §12 |
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
| `SEED_PASSWORD_<USERNAME>` | optional | Sets one account's own password (12+ characters, different for each account), e.g. `SEED_PASSWORD_DEMO_PREPARER` for `make demo-reset` and safety_v2. Every other account gets a random first password in `var/initial-passwords.txt` (ADR 0038). A shared `SEED_PASSWORD` is no longer used |
| `LLM_ENABLED` | optional | `false` runs everything without a model (template narratives) |
| `CORPUS_CONTACT_EMAIL` / `CORPUS_CONTACT_URL` | optional | Added to the harvester's User-Agent so a site admin can reach you rather than block you |
| `LLM_API_KEY`, `EVAL_API_KEY`, `EMBED_API_KEY` | course only | From the course portal |
| `LLM_CA_CERT`, `EMBED_CA_CERT` | course only | Absolute paths, e.g. `~/.credassure/certs/vm06-ca.crt`, `vm02-ca.crt` |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | with tracing | From your self-hosted Langfuse project (§7) |

Rules:
- **Never commit `.env`**, never paste it into a chat, and never ask the coding tool to read it (a hook blocks it).
- Keep certificates **outside the repo** (`mkdir -p ~/.credassure/certs && chmod 700 ~/.credassure`).
- Don't put `MODELS` or `E2E_*` in `.env`. `MODELS` is a make variable (§5), and the e2e targets set their own URLs (§8).

---

## 4. Install

```bash
make install     # uv sync --all-packages --all-extras: every member, dev group, extras (rerank)
npm ci           # npm workspaces from package-lock.json (npm install would rewrite the lock)
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
make hr-db        # rebuild the gitignored hr.db from frozen hr/profiles.json (data/frozen/v1 is committed; `make data` refuses once frozen)
make db           # migrate var/case.db + var/corpus.db, create the accounts in tenant "demo" (own first passwords: var/initial-passwords.txt)
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

### One command
```bash
make start                          # course endpoint Qwen3-8B (VPN), Langfuse if set up, API :8000, web :3000
make start MODELS=local             # local Ollama qwen3:8b instead (the evaluated model, ADR 0036); or MODELS=hf
make start ARGS="--no-model"        # no model (LLM_ENABLED=false); --no-langfuse, --no-ui, --install also work
make stop                           # from another terminal (Ctrl-C in the first one does the same)
```
`scripts/start.sh` checks the tools and that `.env` exists (it never reads it; the course keys and `LLM_CA_CERT` stay
there), installs what is missing, builds `hr.db` and, on first run, `var/case.db` with the users and no cases
(`make db`). For the course endpoint it checks that both hosts answer (VPN); for `MODELS=local` it starts Ollama with
`OLLAMA_CONTEXT_LENGTH=8192` and loads the model. It starts Langfuse when Docker is running and
`deploy/env/langfuse.env` is filled in (the web app then moves to :5173), starts the API and waits for
`/v1/health/ready`, then the web app, and prints the URLs. Logs: `var/start/`. Ctrl-C stops the API, the web app and
an Ollama it started; Langfuse keeps running (`make langfuse-down`). Only `make start` defaults to the course endpoint:
`make run-api`, `make eval` and the scored runs keep `MODELS=local`.

### Step by step

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

Every account has its own password. The first ones are in `var/initial-passwords.txt` (readable only by you): hand each
one to its owner, then delete the file. Each is asked to change it at first sign-in; approvers then set up the
authenticator app. `make passwords` issues new ones (it signs those accounts out; MFA stays set up).

| Username | Role | Can do |
|---|---|---|
| `demo.preparer`, `demo.preparer2`, `prep.e001` … `prep.e020` | Preparer | Create a case, upload files, run stages, answer pauses, ask the copilot |
| `demo.director` | Director, Finance | Approve, reject or return proposals **below** ₹1.5 crore |
| `demo.vp` | VP, Finance | Approve, reject or return proposals **above** ₹1.5 crore and held boundary cases |
| `demo.evaluator` | Evaluator | Run evaluations, read traces and the audit log, retry a stage |

Maker-checker: whoever prepares a case can't approve it. `prep.e0xx` users map to the 20 HR profiles, so some fail onboarding by design (expired training, wrong role and so on).

### Sign in and test (teammates)
Step-by-step guide: **[docs/setup/e2e-testing.md](docs/setup/e2e-testing.md)**. Test data for every use case:
**[data/test-pack/](data/test-pack/)** (an Excel workbook, lender PDFs and lender files per scenario, with the expected
result of each).

```bash
# .env (edit it yourself): MFA_ENFORCED=true and MFA_ENCRYPTION_KEY=<32 random bytes, base64> for two-step sign-in
make db                       # first time: every account gets its own first password
make passwords                # later: new first passwords for all 25 seeded accounts (MFA set-up is kept)
cat var/initial-passwords.txt # username, role, first password; hand each out privately, then delete the file
BOOTSTRAP_ADMIN_PASSWORD='<12+ chars, not containing admin>' make admin NAME=it.admin   # first IT admin, once
make start                    # then open http://localhost:3000
```
1. Sign in with the first password; choose your own. Directors, VPs and the admin then scan the QR code with Google
   or Microsoft Authenticator and keep the backup codes.
2. As `demo.preparer`: **New case** → pick the scenario's workbook and lender PDFs (or lender files) → **Create case**
   → **Workflow → Run**. Compare with the expected result in the guide.
3. As `demo.director` / `demo.vp`: **Approval inbox** → the case → **Review & approval**. The VP's approval above
   ₹1.5 crore asks for the password and a fresh code.
4. Lost a password: nobody can read it back. `make passwords` re-issues the seeded accounts; the admin uses
   **User management → Reset password / Reset MFA** for anyone.

The user manual (PDF, with screenshots of every screen) and the walk-through video are shared with the team in the
Project; they show the same flows.

### Author a case in Excel
```bash
make case-from-xlsx FILE=my_case.xlsx OUT=var/my_case   # validated like an upload; errors by tab, row, column
make case-template                                      # regenerate data/templates/case_template.xlsx
```
Copy `data/templates/case_template.xlsx` (the shaded rows are the CA-2026-0016 demo example), fill it in, convert it,
then upload the files from OUT. OUT can't be under `data/frozen/`. Details: [docs/help/case-authoring.md](docs/help/case-authoring.md).

### Tracing (Langfuse, self-hosted)
```bash
cp deploy/env/langfuse.env.example deploy/env/langfuse.env   # replace every CHANGEME
make langfuse-up             # UI on http://localhost:3000; create a project, put its keys in .env
make langfuse-down
```
Langfuse takes :3000, so run the web UI on 5173 meanwhile (§12). `TRACING_ENABLED=false` turns tracing off.

### Everything in Docker
```bash
make up                      # gateway :8000, web :5173, Ollama, Langfuse (dev profile)
make down
make compose-test            # gateway with the LLM off, no tracing
make compose-demo            # gateway in demo mode + Langfuse
make ollama-pull             # pulls into the Ollama container when it is running
```

### Operations
```bash
make backup                          # online SQLite backup → var/backups/<time>/ (safe while the API runs)
make restore FROM=var/backups/<dir>  # stop run-api first; verifies hashes, keeps a pre-restore copy
make demo-reset                      # recreate the demo cases (stop run-api first)
REPLAY_MODE=true make run-api        # demo fallback: recorded chat replies only, chat endpoint never called
make release VERSION=1.0.0           # var/release/v1.0.0/: RELEASE.json, CycloneDX SBOM, eval reports
make pin-images ARGS=--check         # list images not pinned to a digest (make pin-images pins them)
```
Incidents (endpoint down, quota, locked DB, corpus missing, demo reset): [docs/deployment/RUNBOOK.md](docs/deployment/RUNBOOK.md).

---

## 8. Tests and quality checks

```bash
make check-fast    # ruff + PROGRESS.md check + tests not marked slow (the coding tool stop hook runs this)
make check         # ruff, ruff format, mypy --strict, pytest (incl. the slow Schemathesis fuzz), corpus refs, bandit, import-linter, PROGRESS.md check. Must be green before commit
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
| `make eval` | Full 100-item harness through the API (`ARGS="--fake"` checks mechanics only) |
| `make eval-ablations` | Ablations A1–A6 on the categories each affects |
| `make eval-judge` / `make eval-kappa` | Judge J1 on free-text answers (`SAMPLE=all` exports every judged answer), then κ against the human labels |
| `make eval-report` | E13 report: full system vs best baseline, ablation effects (BRD §12 claim rule), failure taxonomy, cost |
| `make load-smoke` | 10 concurrent demo cases; p95 per stage (Q6: funding < 60 s) |
| `/eval E1 … E18` | The coding tool evaluation reports, saved to `evaluation/reports/` |
| `/freeze-g1` | Writes `evaluation/FROZEN.sha256`, **only after** the human checks are done |

Frozen artefacts: the 100-item test set (25/10/15/15/5/6/8/8/3/5 by BRD §13 category), 40 retrieval queries (v1.0 + v1.1-silver), 20 red-team prompts, bad-citation fixtures, the RBI KFS APR illustration, and `data/frozen/v1`.

Results on the submitted code (local `qwen3:8b`, K3 run `20261124T220648`, 24 Nov; full detail in
[`evaluation/reports/G4-2026-11-24.md`](evaluation/reports/G4-2026-11-24.md)):
- **88/100** on the frozen test set, against **23/100** for the best single-prompt baseline (S2) on the same model.
- Every calculation, gate and safety category at target: onboarding **10/10**, cash flow **15/15**, offers **15/15**,
  negotiation **5/5**, routing **6/6**, injection **8/8**, refusal **8/8**, isolation **3/3**, end to end **5/5**.
- Regulatory answers **13/25** strict (target 20); **16/25** correct in substance by two human labellers. Judge J1
  agrees with them on 17/19 (Cohen's kappa **0.789**, K4).
- Ablations: handing arithmetic (A1) or gate decisions (A4) back to the model loses 31 and 32 items; the ledger and
  Critic (A2) do not move the score but turn unsupported answers into abstentions.
- Retrieval recall@5: **22/40** frozen, **17/20** dev split (ADR 0042). Red team: **25/25** resisted.
- Traces: every case run and evaluation item in Langfuse (K7, links and screenshots in the G4 report).
- safety_v2 (40 items) and the guardrails-off ablation A6 (K5): reviewed by a teammate and frozen before the run; results added when run.

The silver figure is high partly because silver labels and the retriever share signals; the human κ check measures that.

---

## 10. Working with the coding tool, Cursor or other AI tools

**Taking over or continuing a module?** Follow [docs/setup/team-handoff.md](docs/setup/team-handoff.md). It covers where the context lives, the handoff steps, a kickoff prompt for any tool, the guardrail checklist and the module map.

| Tool | Loads automatically | Guardrails |
|---|---|---|
| The coding tool | the project rules (+ the docs and rules it imports), the tool configuration | Enforced by hooks |
| Cursor | the tool configuration, the project rules | Manual checklist (handoff §4) |
| Codex, Copilot, Windsurf, Gemini… | the project rules | Manual checklist (handoff §4) |

Open the coding tool in the repo root; it loads `the project rules` automatically.

- **Build prompts:** `prompts/00–26` (phases), `the build prompt` (UI U0–U6), [docs/build/PHASE_PROMPTS.md](docs/build/PHASE_PROMPTS.md). One phase per session; stop at its gate.
- **Commands:** `/status`, `/next`, `/phase <n>`, `/gate <G>`, `/eval <E#>`, `/review`, `/ui U<n>`, `/freeze-g1`.
- **Progress:** read `PROGRESS.md` first; it is **generated**. The coding tool adds one entry file in `docs/progress/entries/`, updates the module file and runs `make progress`; the tool configuration denies hand edits of `PROGRESS.md` (§11).
- **Subagents** (the tool configuration): `brd-conformance`, `security-reviewer`, `money-auditor`, `test-writer`, `eval-analyst`.
- **Hooks** (the tool configuration): `guard_paths.py` (blocks `.env`, certificates, raw corpus, frozen sets), `guard_bash.py` (blocks `git push`, recursive force delete, printing `.env`), `format_python.py`, `check_before_stop.py` (runs `make check-fast`).

Working rules:
- **The coding tool never pushes.** You review the diff and push yourself.
- Never paste secrets or passwords into a prompt.
- Synthetic data only: no real customer, PAN, Aadhaar or account data, ever.
- No code path may accept, sign or submit a lender offer. Negotiation produces drafts for a human.
- A change to a frozen artefact needs a new version (v2) and an ADR, never an in-place edit.
- Commit messages carry requirement IDs, e.g. `phase-9c-b: lendwise negotiation [LW-12, LW-13]`.

---

## 11. Team workflow: branches, PRs and progress

Six people work on different modules at the same time. Two rules keep that conflict-free: **everyone works on their own branch**, and **nobody edits `PROGRESS.md` by hand**.

### Branches and pull requests
| Rule | How |
|---|---|
| One branch per person and phase | `feature/<module>-<phase>`, e.g. `feature/copilot-p4`, created from an up-to-date `main` |
| One PR per phase | Raised at the phase's stop point, after `make check` and the reviewer subagents pass |
| Merge commits only | Squash and rebase are disabled in GitHub settings: evaluation reports and progress entries cite commit hashes, and squash or rebase would change them |
| CI on every PR | `.github/workflows/ci.yml` (ADR 0028) runs `make check`, openapi-diff, eval-fast on prompt changes, audit and the web build — the same gates as `.githooks/pre-push` (ADR 0027) |
| Resync after every merge | `git switch <your-branch> && git pull origin main` |
| The coding tool never pushes | You review the diff, push, and open the PR |
| Code owners review their module | `.github/CODEOWNERS` requires the module owner's approval |

### Where progress lives
| What | Where | Who edits |
|---|---|---|
| Live task status (who is doing what now) | **CredAssure Post-10b Plan** Sheet | Each owner, their own rows |
| Evidence: commits, eval reports, decisions, open items | `docs/progress/` in the repo | Each owner, through their PR |
| The combined view | `PROGRESS.md` | **Nobody: generated by `make progress`** |

```
docs/progress/
  HISTORY.md          # everything up to 18 Nov 2026, frozen
  modules/            # one file per module: owner, phases, status, open items
    ui.md  copilot.md  auth.md  rai.md  guardrails.md  deployment.md  docs.md  evaluation.md
  entries/            # one new file per PR, never edited by anyone else
    TEMPLATE.md
    2026-11-18-s1-1-progress-tracking-pritish.md
  gates.md            # gate checklist, edited only when a gate is decided
PROGRESS.md           # GENERATED — do not edit
```

### Entry file (one per PR)
Name: `YYYY-MM-DD-<phase>-<step>-<slug>-<owner>.md`, copied from `entries/TEMPLATE.md`:
```markdown
---
phase: P4
step: "4.1"
module: Copilot            # UI | Copilot | Authentication | Responsible AI |
                           # AI Security and Guardrails | Deployment | Documentation | Evaluation
owner: Suresh
commits: [abc1234]
evals: [E8]
status: done               # done | in_progress | blocked
---
- Built: contextual headers on section chunks; one re-ingest; chunk_ids unchanged
- Decisions: ADR 0028
- Open: reranker waits for mentor approval
```

### Every PR, in order
1. `git pull origin main` into your branch.
2. Add **one** entry file in `docs/progress/entries/` and update **your own** module file in `docs/progress/modules/`.
3. `make progress` to regenerate `PROGRESS.md`.
4. `make check-fast`. It (and CI) fails if `PROGRESS.md` doesn't match the generated output, or if an entry's front matter is invalid.
5. Commit, push, open the PR, and update your rows in the plan Sheet.

### If `PROGRESS.md` conflicts during a merge
Don't resolve it by hand. Take either side, run `make progress`, and commit the regenerated file. Entry and module files can't conflict, because each one is written by only one person.

### the coding tool
`the project rules` and every `prompts/*.md` tell the coding tool to write an entry file and update the module file, never `PROGRESS.md` itself. Each phase report it gives you should name the entry file it created.

---

## 12. Troubleshooting

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

## 13. Repository layout

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
├── prompts/                # the coding tool build prompts 00–26 (agent prompts live in agents/*/prompts/)
├── deploy/                 # env profiles, Dockerfiles, compose, nginx, backup/restore scripts
├── docs/                   # requirements, architecture, adr, data, setup, security, ui, build
├── the tool configuration  .github/
└── PROGRESS.md (generated)  Makefile  pyproject.toml  package.json  openapi.json
```

---

## 14. Status, data and licences

**Gates**
- **G1:** provisionally frozen. Final after human judging and κ, the gold hand check, the APR second transcription, remaining owner names and the course baseline.
- **G2:** passed (2026-11-15).
- **G3, G4:** pending.

**Done:** Phases 1–10b, UI U0–U6 (U6 live checks pending: H15, H16), and plan v3.4 P0–P5 and P7–P10 (guardrails, copilot v2, evaluation harness,
security and fairness, RAI UI, ship and RAI documents). Version **1.0.0** (`CHANGELOG.md`).

**Next:** the live runs on the model (E13 full evaluation, ablations, J1 κ, safety_v2 after its freeze, load smoke) for
Gate G4 (P11), then the report, slides and demo (P12). P6 (course endpoint) waits for agreement. Open team decisions:
[docs/plan/human-review.md](docs/plan/human-review.md).

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
| `RERANKER` | `none` | none, local_cross_encoder, llm_pointwise | ADR 0013, 0032 |
| `APR_CONVENTION` | `nominal` | nominal, effective | ADR 0012 |
| `BOUNDARY_RULE` | `hold` | hold, director, vp | Exactly ₹1.5 crore routing (APR-03) |
| `APPROVAL_STEP_UP` | `true` | bool | Approving above ₹1.5 crore asks for the password again (NFR-07) |
| `PLANNER_MODE` | `fixed` | fixed, llm_proposes | Scope #19; code validates any proposal |
| `COPILOT_SEARCH_MODE` | `hybrid` | hybrid, keyword | Copilot retrieval |
| `FEATURE_STRETCH` | `false` | bool | BRD §4.2 stretch items |
| `ABLATION` | empty | A1..A6 | Evaluation only (BRD §12); A6 (guardrails off) is refused in the demo profile |
| `REPLAY_MODE` | `false` | bool | Demo fallback: recorded model replies only (ADR 0015) |

> **Not financial or legal advice.** CredAssure is an academic prototype. Every proposal requires human approval, and the system never commits a business to a lender.
