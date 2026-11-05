.DEFAULT_GOAL := help
PY_SRC := apps/gateway/src $(wildcard agents/*/src) \
	$(filter-out packages/api-client/src,$(wildcard packages/*/src)) evaluation/src \
	data/generators/src
COMPOSE := docker compose -f deploy/compose/compose.yaml
# Settings for corpus network runs (CORPUS_CONTACT_EMAIL, ADR 0020) come from .env when it exists.
ENV_FILE := $(if $(wildcard .env),--env-file .env,)
PNPM := $(shell command -v pnpm >/dev/null 2>&1 && echo pnpm || echo "npx --yes pnpm@9.15.0")

.PHONY: testset help install check check-fast test run-api run-ui data ingest eval baseline openapi client \
        db demo-reset up down audit corpus-audit corpus-harvest corpus-download corpus-import corpus-verify corpus-manual corpus-report corpus-dates corpus-status corpus-export corpus-ingest compose-dev compose-test compose-demo langfuse-env-check \
        langfuse-up langfuse-down ollama-pull backup restore

help:  ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install:  ## Sync the uv workspace (all members + dev group)
	uv sync --all-packages

check:  ## ruff, ruff format, mypy --strict, pytest, bandit
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy --strict $(PY_SRC)
	uv run pytest -q
	uv run python -m credassure.evaluation.check_corpus_refs
	uv run bandit -q -c pyproject.toml -r $(PY_SRC)
	uv run lint-imports

check-fast:  ## ruff + fast tests (used by the Claude stop hook)
	uv run ruff check .
	uv run pytest -q -m "not slow"

test:  ## Full test suite with coverage
	uv run pytest --cov=credassure --cov-report=term-missing

audit:  ## Dependency vulnerability audit
	uv run pip-audit --skip-editable

ollama-pull:  ## Download llama3.1:8b and nomic-embed-text (ADR 0017; not part of make check)
	@if $(COMPOSE) --profile dev ps --status running --services 2>/dev/null | grep -qx ollama; then \
		$(COMPOSE) --profile dev exec ollama ollama pull llama3.1:8b; \
		$(COMPOSE) --profile dev exec ollama ollama pull nomic-embed-text; \
	elif command -v ollama >/dev/null 2>&1; then \
		ollama pull llama3.1:8b; \
		ollama pull nomic-embed-text; \
	else \
		echo "No Ollama found. Install it and run 'OLLAMA_CONTEXT_LENGTH=8192 ollama serve', or start 'make compose-dev'."; \
		exit 1; \
	fi

run-api:  ## FastAPI on :8000 (docs at /docs)
	uv run uvicorn credassure.gateway.main:app --factory --reload --port 8000

openapi:  ## Export openapi.json (ADR 0004)
	uv run python -m credassure.gateway.openapi

client: openapi  ## Generate the TypeScript API client from openapi.json
	$(PNPM) --filter @credassure/api-client generate

up: langfuse-env-check  ## Gateway, web, Ollama and Langfuse (dev profile)
	$(COMPOSE) --profile dev --profile langfuse up --build

down:  ## Stop the dev stack
	$(COMPOSE) --profile dev --profile langfuse down

backup:  ## Database backup (Phase 12)
	deploy/scripts/backup.sh

restore:  ## Database restore (Phase 12)
	deploy/scripts/restore.sh

LANGFUSE_ENV := deploy/env/langfuse.env

langfuse-env-check:
	@test -f $(LANGFUSE_ENV) || { echo "Missing $(LANGFUSE_ENV): copy $(LANGFUSE_ENV).example and set every value"; exit 1; }
	@! grep -q CHANGEME $(LANGFUSE_ENV) || { echo "$(LANGFUSE_ENV) still contains CHANGEME placeholders"; exit 1; }

compose-dev: langfuse-env-check  ## Gateway + Langfuse (dev profile)
	$(COMPOSE) --profile dev --profile langfuse up --build

compose-test:  ## Gateway with LLM disabled (template fallbacks), no tracing; FakeLLM lands in Phase 6
	$(COMPOSE) --profile test up --build

compose-demo: langfuse-env-check  ## Gateway in demo mode + Langfuse (replay lands in Phase 12, ADR 0015)
	$(COMPOSE) --profile demo --profile langfuse up --build

langfuse-up: langfuse-env-check  ## Self-hosted Langfuse only (ADR 0016)
	$(COMPOSE) --profile langfuse up -d

langfuse-down:
	$(COMPOSE) --profile langfuse down

run-ui:  ## Vite dev server for the React stub
	$(PNPM) --filter @credassure/web dev

data:  ## Seeded synthetic data -> data/frozen/v1 + hr.db (Phase 2, idempotent)
	uv run python -m credassure.datagen

corpus-audit:  ## Legal-basis and schema audit of data/corpus/manifest.yaml (scope #14, ADR 0019)
	uv run python -m credassure.datagen.harvest audit

corpus-harvest:  ## Harvest script sources' index pages into manifest entries (network, 1 req/s)
	uv run $(ENV_FILE) python -m credassure.datagen.harvest harvest

corpus-download:  ## Download pending script entries; blocked hosts go to MANUAL_DOWNLOADS.md (network)
	uv run $(ENV_FILE) python -m credassure.datagen.harvest download

corpus-import:  ## Ingest files saved by hand in data/corpus/raw/ (<doc_id>.pdf|html), then audit
	uv run python -m credassure.datagen.harvest import

corpus-verify:  ## Check local raw files against the lock-file SHA-256 (team drive sync)
	uv run python -m credassure.datagen.harvest verify

corpus-manual:  ## Regenerate MANUAL_DOWNLOADS.md (six owner sections)
	uv run python -m credassure.datagen.harvest manual

corpus-dates:  ## Extract effective dates for available docs; write DATE_REVIEW.md (10% human sample)
	uv run python -m credassure.datagen.harvest dates

corpus-export:  ## Write data/corpus/CORPUS_INDEX.md and .xlsx (one row per manifest entry + summary)
	uv run python -m credassure.datagen.harvest export

corpus-docker-%:  ## Run a corpus target in the hardened container, e.g. make corpus-docker-download (ADR 0020)
	$(COMPOSE) --profile tools run --rm corpus make corpus-$*

corpus-status:  ## One screen: real available vs 500, by source and owner; also regenerates CORPUS_INDEX.md/.xlsx
	uv run python -m credassure.datagen.harvest status

corpus-report:  ## Real corpus table: planned, available, manual pending, distance to 500
	uv run python -m credassure.datagen.harvest report

corpus-ingest: ingest  ## Alias so `make corpus-docker-ingest` runs Phase 7 ingestion in the container

ingest:  ## Download, hash and index the corpus (Phase 7)
	@echo "ingest: not implemented until Phase 7"; exit 1

eval:  ## Run the 100-item test set through the API (Phase 11)
	@echo "eval: not implemented until Phase 11"; exit 1

baseline:  ## Prompt baselines S1-S3 on the 100 items (EVAL_BASE_URL / EVAL_MODEL; default local Ollama, ADR 0017)
	uv run $(ENV_FILE) python -m credassure.evaluation.baseline.run --strategy all

testset:  ## Rebuild evaluation/testset/v1 and the retrieval/red-team/fixture assets (refuses once frozen)
	uv run python -m credassure.evaluation.build_testset
	uv run python -m credassure.evaluation.build_assets

db:  ## Migrate var/case.db + var/corpus.db and seed users (needs SEED_PASSWORD; ADR 0005, scope #29)
	uv run python -m credassure.ledger.migrate upgrade case var/case.db
	uv run python -m credassure.ledger.migrate upgrade corpus var/corpus.db
	uv run $(ENV_FILE) python -m credassure.ledger.seed var/case.db

demo-reset:  ## Reset demo data and replay cache (Phase 12)
	deploy/scripts/demo-reset.sh
