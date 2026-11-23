# Local development

Prerequisites: [prerequisites.md](prerequisites.md). Settings: [environment.md](environment.md).
Continuing someone's module with Claude Code, Cursor or another AI tool: [team-handoff.md](team-handoff.md).

## Install
```bash
make install                 # uv sync --all-packages --all-extras (never a bare `uv sync`: it drops the rerank extra)
npm install                  # apps/web + packages/api-client
cp .env.example .env         # then set JWT_SECRET (32+ chars) and SEED_PASSWORD (12+ chars)
make hr-db && make db && make ingest
```
`data/frozen/v1` is committed and frozen (G1), so `make data` refuses to regenerate it; `make hr-db` rebuilds the gitignored
`data/frozen/v1/hr.db` from the frozen `hr/profiles.json`. `make db` migrates `var/case.db` and
`var/corpus.db` and seeds users in tenant `demo`. `make ingest` builds the search index for the current `MODELS` profile.

## Run everything
`make start` connects to the course endpoint (`MODELS=local` for Ollama), starts Langfuse when it is set up, the API
and the web app, waits until each answers and prints the URLs; `make stop` (or Ctrl-C) stops them. It creates the
database with the users on first run and no cases. Options and details: [README §7](../../README.md#7-run-the-app).
The sections below are the same steps one at a time.

## Run the API
```bash
OLLAMA_CONTEXT_LENGTH=8192 ollama serve    # skip with LLM_ENABLED=false
make run-api                               # http://localhost:8000, Swagger at /docs
curl -s localhost:8000/v1/health/ready     # databases, model circuit, quota
```
`make run-api` sets `TENANT_ID=demo` and reloads on code changes. For the course model add `MODELS=course`.

## Run the web app
`make run-ui` starts the Next.js dev server on **http://localhost:3000** (`npm run dev -w apps/web`). The gateway's
default CORS origins include `http://localhost:3000` and `http://localhost:5173`; use one of them so sign-in works.
Langfuse also uses :3000: run the UI on 5173 with `npm run dev -w apps/web -- -p 5173`.

## Demo data
Stop the API, then `make demo-reset` (10 demo cases through the real API, idempotent), then start the API again.
Users and cases: [README §6–§7](../../README.md#6-data-databases-corpus-demo-cases).

## After an API change
```bash
make openapi && make client     # openapi.json + generated TypeScript client
```
CI fails on a stale `openapi.json`.

## Before every commit
`make check` (ruff, format, mypy --strict, pytest, corpus refs, bandit, import-linter) must be green. `make check-fast` is the quick loop.

## End-to-end tests
They use their own database and ports, so they never touch the demo data:
```bash
make e2e-db && make run-api-e2e     # API on :8001 (second terminal)
make run-ui-e2e                     # UI on :3001 (third terminal)
make e2e                            # Playwright; PW_ARGS="--project=u3" for one project
```
