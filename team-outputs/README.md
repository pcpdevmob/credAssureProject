# CredAssure

**Agentic MSME working-capital loan proposal workflow**, built for the IIT Kharagpur Executive PG Programme in Generative AI and Agentic AI (Capstone **Track B**: an API-side multi-agent system on a hosted ≤8B model).

> **The design rule:** the model reads, explains and drafts. Code calculates, routes and gates. A human approves.

CredAssure (formerly *FinBridge AI*) takes an MSME working-capital case through four stages:
1. It confirms the preparer is trained and authorised.
2. It sizes the working-capital need from a 26-week cash-flow forecast.
3. It audits and ranks lender offers by APR, including the Key Fact Statement (KFS).
4. It verifies every number and citation.

Code then routes the proposal to the right approver. The model never decides, never computes a figure, and never accepts, signs or submits a lender offer.

---

## Contents
1. [Agents and owners](#1-agents-and-owners)
2. [Prerequisites](#2-prerequisites)
3. [Get the code](#3-get-the-code)
4. [Configure `.env`](#4-configure-env)
5. [Install](#5-install)
6. [Local model (Ollama)](#6-local-model-ollama)
7. [Data: database, corpus, demo cases](#7-data-database-corpus-demo-cases)
8. [Run the app](#8-run-the-app)
9. [Tests and quality checks](#9-tests-and-quality-checks)
10. [Evaluation](#10-evaluation)
11. [Working with the coding tool](#11-working-with-the-coding-tool)
12. [Team workflow: branches, PRs and progress](#12-team-workflow-branches-prs-and-progress)
13. [Troubleshooting](#13-troubleshooting)
14. [Repository layout](#14-repository-layout)
15. [Status, data and licences](#15-status-data-and-licences)

---

## 1. Agents and owners

| Agent | Package | Job | Owner |
|---|---|---|---|
| Supervisor and routing | `agents/supervisor` | Fixed stage order, code gates, re-check of every GO, pause and resume, approval wait, routing by amount | [Name 1] |
| Employee Onboarding | `agents/onboarding` | Checks from HR records that the preparer's role, required trainings and policy acknowledgements are in place | Tejas |
| Working Capital | `agents/working_capital` | 26-week forecast, peak shortfall, cash buffer, financing need | Suresh |
| LendWise | `agents/lendwise` | KFS hidden-charge audit, APR by IRR (GST, insurance, CGTMSE), affordability, ranking, negotiation drafts | Pritish |
| Critic / Verifier | `agents/critic` | Number normaliser checked against the ledger, citation checks, banned content, regenerate ×2 then template fallback | Abhishek |
| Regulatory Copilot | `agents/copilot` | Hybrid RAG over 1,084 real Indian documents, with cited answers and refusals | [Name 6] |

Shared code: `packages/core` (contracts, ports, the `AgentResult` from ADR 0018), `packages/llm` (model client), `packages/retrieval`, `packages/engines` (deterministic money, APR and routing maths), `apps/gateway` (FastAPI), `apps/web` (React), `packages/api-client` (generated TypeScript client).

Module owners for the remaining work (plan v3.4): Guardrails and RAI docs Pritish · Copilot retrieval Suresh · Copilot answering Tejas · Security and safety_v2 Abhishek and Tejas · UI the UI lead.

---

## 2. Prerequisites

| Tool | Version | Install (macOS) | Notes |
|---|---|---|---|
| git | any recent | Xcode CLT | |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | Manages Python and the workspace |
| Python | 3.12 | `uv python install 3.12` | Don't use the system Python |
| Node.js + **npm** | Node 20 LTS | `brew install node@20` or nvm | **npm only, never pnpm or yarn.** Don't run `corepack enable`; it interferes with mobile toolchains |
| Ollama | latest | https://ollama.com/download | Local model until integration is complete |
| Docker | optional | Docker Desktop | Only for the container build and deployment checks |
| The coding tool | latest | see the tool vendor docs | For building; see §11 |
| make, openssl, sqlite3 | system | preinstalled on macOS | |

Hardware: a 16 GB Apple Silicon Mac runs `qwen3:8b` fully on the GPU at an 8K context.

---

## 3. Get the code

```bash
git clone <your-repo-url> CredAssure
cd CredAssure
```

If you're starting from the build kit instead of the repo, copy **including hidden folders** (the tool configuration, `.github/`):

```bash
cp -R <path-to-credassure-build-kit>/. ./
```

> `cp -R <src>/* ./` silently skips the dot-folders. Always use `<src>/.`.

---

## 4. Configure `.env`

```bash
cp .env.example .env
```

**Required even for local runs:**

```bash
# JWT_SECRET is the key that signs login tokens. The API refuses to start without it.
sed -i '' '/^JWT_SECRET=$/d' .env          # macOS; on Linux use: sed -i '/^JWT_SECRET=$/d' .env
printf 'JWT_SECRET=%s\n' "$(openssl rand -hex 32)" >> .env
```

Then edit `.env` by hand:

| Key | When | Value |
|---|---|---|
| `SEED_PASSWORD_<USERNAME>` | optional | One account's own password (12+ characters, never shared). Others get a random first password in `var/initial-passwords.txt` |
| `MODELS` | always | `local` (default) or `course` |
| `CORPUS_CONTACT_EMAIL` / `CORPUS_CONTACT_URL` | optional | Goes into the polite User-Agent the harvester sends, so a site admin can reach you rather than block you |
| `LLM_API_KEY`, `EVAL_API_KEY`, `EMBED_API_KEY` | course only | From the course portal |
| `LLM_CA_CERT`, `EMBED_CA_CERT` | course only | Absolute paths to the course CA certificates, e.g. `~/.credassure/certs/course-ca.pem` |

Rules:
- **Never commit `.env`**, never paste it into a chat or prompt, and never ask the coding tool to read it. the tool configuration denies `Read(./.env)`.
- Keep certificates **outside the repo and outside Downloads** (`mkdir -p ~/.credassure/certs && chmod 700 ~/.credassure`).
- Don't put `E2E_*` URLs in `.env`. The e2e targets set them themselves (§9).

### Model profiles
`MODELS=local|course` loads `deploy/env/models-<profile>.env` **on top of** `.env`:

| | `models-local.env` | `models-course.env` |
|---|---|---|
| Chat model | `qwen3:8b` via Ollama `http://localhost:11434/v1` | Course ≤8B endpoint |
| Thinking off | `reasoning_effort: "none"` | `chat_template_kwargs: {enable_thinking: false}` |
| Context | 8192 | from `make llm-probe` |
| Embeddings | local Ollama embedding model | course embeddings endpoint |

The `/no_think` prompt tag is ignored by Ollama. `reasoning_effort` is what keeps explanations at 1.5–4 s instead of 17–65 s.

---

## 5. Install

```bash
make install
```

This runs `uv sync --all-packages` (every workspace package), then `npm install` at the root (the npm workspaces `apps/web` and `packages/api-client`), and installs the pre-commit hooks.

> **Never run a bare `uv sync`.** It removes workspace packages that aren't root dependencies, and imports then break at random.

---

## 6. Local model (Ollama)

```bash
make ollama-pull                        # pulls qwen3:8b and the embedding model
OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_KEEP_ALIVE=30m ollama serve
```

Leave that terminal open. In another terminal, check it:

```bash
ollama run qwen3:8b --think=false "Reply with OK" --verbose
ollama ps          # expect CONTEXT 8192 and PROCESSOR 100% GPU
```

If `ollama ps` shows a 4096 context, the server was started without `OLLAMA_CONTEXT_LENGTH`. If you'd rather run Ollama as the menu-bar app, set the variables for launchd once:

```bash
launchctl setenv OLLAMA_CONTEXT_LENGTH 8192
launchctl setenv OLLAMA_KEEP_ALIVE 30m
# then quit and reopen the Ollama app
```

**"address already in use" on :11434** (the app and the CLI are both running):

```bash
killall Ollama; pkill -f "ollama serve"; pkill -f "ollama runner"
lsof -i :11434        # should print nothing; then start ollama serve again
```

---

## 7. Data: database, corpus, demo cases

```bash
make db           # create case.db (WAL), hr.db (read-only) and corpus.db (FTS5); apply migrations; seed users
make ingest       # chunk and embed the corpus into corpus.db + Chroma (local embeddings)
make demo-reset   # restore the 10 demo cases. STOP THE API FIRST.
```

After `make demo-reset` (it prints a table of the 10 cases it created):
- **CA-2026-0016**: the happy path, **awaiting Director approval**.
- **CA-2026-0024**: **paused on the cash-buffer gate** (`min_cash_buffer`), with one question for the preparer.
- Cases 0001–0015 are the frozen evaluation cases from `data/frozen/v1`.

Run `make demo-reset` before every demo rehearsal, with the API stopped. Adding a case to the reset script shifts every later case ID, so check its printed table against `docs/demo/demo-script.md`.

### Corpus
1,084 real Indian documents (target ≥500 met) plus synthetic policies and KFS documents. The sources are RBI, CGTMSE, the e-Gazette, CBIC, India Code (`indiacode.gov.in`), Udyam, data.gov.in and bank charge schedules. The full list is in `docs/DATA_RESOURCES.md` and `CredAssure_Indian_Corpus_Sources.xlsx`.

```bash
make corpus-status    # real / available / manual-pending per source
make corpus-harvest   # polite harvester: robots.txt, 1 request/s, stops on 403/429/challenge
make corpus-import    # import files you saved by hand into data/corpus/raw/
make corpus-verify    # SHA-256 check against corpus.lock
```

Corpus rules (non-negotiable):
- Respect robots.txt; at most one request per second; **stop that host on any block**.
- No spoofed headers, no headless browsers, no CAPTCHA solving, and no bot-block bypass.
- RBI, e-Gazette, incometaxindia and India Code are **downloaded by hand** (see `data/corpus/MANUAL_DOWNLOADS.md`), then imported with `make corpus-import`.
- Run harvesting from a **personal machine and network**, not an employer network.
- **Never commit L3/L4 raw files** (`data/corpus/raw/` is git-ignored). Only the manifest, the lock file and extracted metadata are committed.

---

## 8. Run the app

**Terminal 1: Ollama** (§6)

**Terminal 2: API**
```bash
make run-api                              # FastAPI on http://localhost:8000
curl -s localhost:8000/v1/health/live     # {"status":"ok"}
curl -s localhost:8000/v1/health/ready    # checks the databases, Chroma and the model
open http://localhost:8000/docs           # Swagger
```

**Terminal 3: Web UI**
```bash
npm run dev -w apps/web                   # React on http://localhost:3000
```

Sign in as one of the seeded users with its own first password from `var/initial-passwords.txt`; you are asked to change it.

| Role | Can do |
|---|---|
| Preparer | Create a case, upload files, run stages, answer pauses |
| Reviewer | Read everything, comment |
| Manager | Approve up to ₹1.5 crore |
| Director | Approve above ₹1.5 crore (a case at exactly ₹1.5 crore is **HELD**); re-enters the password to approve (step-up) |
| Admin | Users, configuration, audit verification |

The maker-checker rule applies: whoever prepares a case can't approve it.

**Without a model:** `LLM_ENABLED=false make run-api` runs every gate, calculation, routing and approval. Narratives fall back to templates and the copilot answers "unavailable". The demo must also work in this mode.

### Switching to the course endpoint (after integration)
```bash
# add the course keys and cert paths to .env first (§4)
MODELS=course make llm-probe          # checks reachability, context length, guided-JSON support, limits
MODELS=course make baseline           # graded S1–S3 prompting baseline (G1 evidence)
MODELS=course make ingest CONFIRM=1   # re-embed with the course embedding model (it rebuilds the index)
MODELS=course make retrieval-eval
MODELS=course make run-api
```
Only set `LLM_SUPPORTS_GUIDED_JSON=true` after `llm-probe` confirms guided JSON works.

---

## 9. Tests and quality checks

```bash
make check-fast    # lint + type check + unit tests (no network) + PROGRESS.md check — run before every commit
make check         # full: ruff, mypy --strict, pytest (1,350+ tests), bandit, import-linter, Schemathesis fuzzing
make audit         # pip-audit + npm audit
```

Web:
```bash
npm run typecheck -w apps/web
npm run test -w apps/web          # vitest
npm run build -w apps/web
```

**End-to-end tests (isolated, so they never touch the demo database):**
```bash
make e2e-db         # fresh e2e database
make run-api-e2e    # API on :8001 against the e2e DB
make run-ui-e2e     # UI on :3001 pointing at :8001
make e2e            # Playwright suite
```

**API contract → TypeScript client:** after any change to an API schema:
```bash
make openapi && make client       # regenerates openapi.json and packages/api-client
make openapi-diff                 # fails on a breaking change against main's openapi.json
```

---

## 10. Evaluation

| Command | What it does |
|---|---|
| `make retrieval-eval` | Recall@k for 40 queries × 3 chunkers, RRF fusion. Fails only on a KR-04 violation or a cross-case KFS leak |
| `make retrieval-silver` | Builds silver labels with a blind the coding tool judge |
| `make judge JUDGE=pritish` | Human judging on the 249-item sample (each judge uses their own name) |
| `make kappa` | Plain and weighted κ, human vs silver. The target is weighted κ ≥ 0.7 |
| `make baseline` | Prompting strategies S1–S3 on the frozen test set |
| `make eval-fast` | Prompt-registry hash/version check plus smoke evaluations |
| `/eval E1 … E18` | The coding tool command for the independent evaluation reports (saved in `evaluation/reports/`) |
| `/freeze-g1` | Writes `evaluation/FROZEN.sha256`. **Only after** the human checks are done |

Frozen artefacts: the 100-item test set (split 25/15/15/10/8/8/6/5/5/3), 40 retrieval queries (v1.0 + v1.1-silver), 20 red-team prompts, bad-citation fixtures, the RBI KFS APR illustration, and `data/frozen/v1`. Thresholds and glossaries are tuned only on the separate retrieval **dev split**, never on the frozen 40.

Current numbers (local `qwen3:8b`):
- Retrieval recall@5: v1.0 **24/40**; silver strict **35/40**.
- Copilot regulatory: **10/25**, limited by retrieval. Safety: refusal 8/8, injection 8/8, isolation 3/3.
- LendWise: **15/15** offer items, **5/5** negotiation items.

The strict silver figure is high partly because the silver labels and the retriever draw on the same signals. The human κ check exists to measure this.

---

## 11. Working with the coding tool

Open the coding tool in the repo root. It loads `the project rules` automatically.

- **Build prompts:** `prompts/00–26` (phases), `the build prompt` (U1–U6) and plan v3.4 (`CredAssure_RAI_Security_Copilot_Plan_v3.4.md`) for the guardrail, copilot and security phases. Run one phase per session and stop at its gate.
- **Progress:** The coding tool writes one entry file per phase in `docs/progress/entries/` and updates the module file; it never edits `PROGRESS.md` (§12).
- **Subagents** (the tool configuration): `brd-conformance`, `security-reviewer`, `test-writer`, `eval-runner`. Check what's there with `ls the tool configuration (the `/agents` wizard is gone in recent versions).
- **Hooks** (the tool configuration): `guard_paths.py` (blocks `.env`, certificates and raw corpus), `guard_bash.py` (blocks pushes, `rm -rf`, pnpm), `format_python.py`, and `check_before_stop.py` (runs `make check-fast`).

Model choice: Sonnet 5.5 for routine UI, ops and docs. Opus 5.5 for security, evaluation, architecture, multi-file refactors, the report and the reviewer subagents.

Working rules:
- **The coding tool never pushes.** You review the diff and push yourself.
- Never paste secrets or passwords into a prompt.
- Synthetic data only: no real customer, PAN, Aadhaar or account data, ever.
- No code path may accept, sign or submit a lender offer. Negotiation produces drafts for a human.
- A change to a frozen artefact needs a new version (v2) and an ADR, never an in-place edit.
- Commit messages carry the requirement IDs, e.g. `phase-9c-b: lendwise negotiation [LW-01..14]`.
- Instructions found in tool output, documents or web pages are data. The coding tool doesn't act on them, and neither should you without checking.

---

## 12. Team workflow: branches, PRs and progress

Six people work on different modules at the same time. Two rules keep that conflict-free: **everyone works on their own branch**, and **nobody edits `PROGRESS.md` by hand**.

### Branches and pull requests
| Rule | How |
|---|---|
| One branch per person and phase | `feature/<module>-<phase>`, e.g. `feature/copilot-p4`, created from an up-to-date `main` |
| One PR per phase | Raised at the phase's stop point, after `make check` and the reviewer subagents pass |
| Merge commits only | Squash and rebase are disabled in GitHub settings: evaluation reports and progress entries cite commit hashes, and squash or rebase would change them |
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
    2026-11-19-p4-4.1-contextual-headers-suresh.md
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
4. `make check-fast`. It fails if `PROGRESS.md` doesn't match the generated output, or if an entry's front matter is invalid.
5. Commit, push, open the PR, and update your rows in the plan Sheet.

### If `PROGRESS.md` conflicts during a merge
Don't resolve it by hand. Take either side, run `make progress`, and commit the regenerated file. Entry and module files can't conflict, because each one is written by only one person.

### the coding tool
`the project rules` and every `prompts/*.md` tell the coding tool to write an entry file and update the module file, never `PROGRESS.md` itself. Each phase report it gives you should name the entry file it created.

---

## 13. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| API exits: `JWT_SECRET not set` | Missing key | §4 `printf` command |
| `ModuleNotFoundError: credassure.agents...` | A bare `uv sync` removed workspace packages | `make install` |
| Explanations take 17–65 s | Qwen3 thinking is on | Check `MODELS=local` loads `reasoning_effort: "none"`; restart the API |
| `ollama ps` shows a 4096 context | Server started without the environment variable | §6 (`OLLAMA_CONTEXT_LENGTH=8192`) |
| `bind: address already in use :11434` | App and CLI both running | `killall Ollama; pkill -f "ollama serve"; pkill -f "ollama runner"` |
| osascript error −128 when quitting Ollama | App already closing | Same `killall`/`pkill` line |
| Demo cases look wrong or show e2e junk | e2e ran against the demo DB, or a stale state | Stop the API → `make demo-reset` → restart |
| `make demo-reset` fails: database locked | API still running | Stop `make run-api` first |
| UI calls fail with 401 after a restart | Token signed with an old `JWT_SECRET` | Sign out and in again |
| UI type errors after an API change | Client out of date | `make openapi && make client` |
| `make llm-probe` says variables missing | Course values not in `.env` | Add them (§4); the probe checks only that they're set |
| `make corpus-import` rejects a PDF | Scanned PDF with no text layer | Use the replacement listed in `MANUAL_DOWNLOADS.md` |
| Harvester stops on a host | 403/429/challenge page | Expected: download those by hand. Don't work around it |
| `/offers` or the report shows "stale" | Offers, KFS or an upstream figure changed after the stage ran | Re-run the LendWise stage, then regenerate the report |
| `make check-fast` fails: PROGRESS.md out of date | Someone edited it by hand, or forgot `make progress` | Run `make progress` and commit the result |
| Merge conflict in `PROGRESS.md` | Two branches regenerated it | Take either side, run `make progress`, commit (§12) |
| `make check-fast` fails: invalid entry | Missing or misspelt front-matter field | Fix the entry file against `entries/TEMPLATE.md` |

---

## 14. Repository layout

```
CredAssure/
├── agents/                 # one project per agent, each with src/ + api/ router + tests/
│   ├── supervisor/  onboarding/  working_capital/  lendwise/  critic/  copilot/
├── packages/
│   ├── core/               # contracts (AgentResult, ADR 0018), ports, errors, prompt registry
│   ├── engines/            # deterministic money (paise), APR/IRR, forecast, routing
│   ├── llm/                # OpenAI-compatible client, breaker, limiter, PII redaction
│   ├── retrieval/          # chunkers, BM25 (FTS5) + dense (Chroma), RRF, ADR 0019 filters
│   ├── adapters/           # SqlLedger, tool runner, tracing
│   └── api-client/         # generated TypeScript client (npm workspace)
├── apps/
│   ├── gateway/            # FastAPI /v1, auth, jobs + SSE, RFC 9457 errors
│   └── web/                # React UI (npm workspace)
├── data/
│   ├── corpus/             # manifest.yaml, corpus.lock, MANUAL_DOWNLOADS.md (raw/ git-ignored)
│   ├── frozen/v1/          # synthetic cases, HR store, policies, KFS + SHA256SUMS
│   └── *.db                # local databases (git-ignored)
├── evaluation/             # testset, retrieval queries, gold, judging, redteam, reports, baseline
├── prompts/  (YAML)        # versioned and hashed prompt registry
├── deploy/                 # env profiles, Dockerfiles, nginx, compose
├── docs/
│   ├── progress/           # HISTORY.md, modules/, entries/ (§12)
│   └── ...                 # BRD, architecture (arc42 + C4), ADRs, DATA_*, ui/, demo/, build/
├── the tool configuration  .github/ (CODEOWNERS)
├── PROGRESS.md (generated)  Makefile  pyproject.toml  package.json
```

---

## 15. Status, data and licences

**Gates**
- **G1:** provisional. Waiting on human judging and κ, the gold hand check, the APR second transcription, owner names, the course baseline, and ADR 0018 acceptance.
- **G2:** passed.
- **Skeleton gate:** pending the team walkthrough.

**Done through:** Phases 1–9e, Phase 10a, UI U1–U4 and the demo pack. Phase 10b is in progress.

**Next** (plan v3.4; task-level detail in the **CredAssure Post-10b Plan** Sheet):
- P0 plan and ADRs; P1 close G1; P2 Gate G3;
- P3 guardrails and PII v2; P4–P5 copilot retrieval and answering;
- P6 course-endpoint switch; P7 Phase 11 evaluation; P8 security and safety_v2;
- P9 U5–U6; P10 Phase 12 and RAI docs; P11 G4; P12 report.

**Data**
- All case, HR, offer and KFS data is **synthetic**.
- The corpus is public Indian material only, under these legal bases:
  - **L1:** GODL-India.
  - **L2:** Gazette matter and judgments, under Copyright Act s.52(1)(q).
  - **L3:** Acts. Store locally, quote short passages, never commit.
  - **L4:** public documents and facts, for research use. Short quotes with citation in the app; files never redistributed.
  - **L5:** team-owned.
- ADR 0019 makes the corpus Indian-only. KR-04 distractors are other states' policies, superseded circulars, and directions for other lender types.

**Licences**
- Code: **MIT**.
- Synthetic data, evaluation sets and documentation: **CC BY 4.0**.
- Third-party documents keep their own terms. They are not redistributed in this repo.

> **Not financial or legal advice.** CredAssure is an academic prototype. Every proposal requires human approval, and the system never commits a business to a lender.
