.DEFAULT_GOAL := help
PY_SRC := apps/gateway/src $(wildcard agents/*/src) \
	$(filter-out packages/api-client/src,$(wildcard packages/*/src)) evaluation/src \
	data/generators/src
COMPOSE := docker compose -f deploy/compose/compose.yaml
# Settings for corpus network runs (CORPUS_CONTACT_EMAIL, ADR 0020) come from .env when it exists.
# MODELS=local (default, Ollama qwen3:8b + in-process bge-small) | course (graded endpoints).
# The profile loads after the dotenv file, so it wins for model settings; keys and CA paths stay there.
MODELS ?= local
MODELS_FILE := deploy/env/models-$(MODELS).env
ifeq ($(wildcard $(MODELS_FILE)),)
$(error MODELS=$(MODELS): no $(MODELS_FILE); use local or course)
endif
ENV_FILE := $(if $(wildcard .env),--env-file .env,) --env-file $(MODELS_FILE)
# The dev/demo database (var/case.db) is tenant "demo" (make demo-reset); an exported variable beats --env-file.
DEMO_TENANT := TENANT_ID=demo

.PHONY: redteam rag-baseline load-smoke eval-judge eval-kappa eval-report eval-ablations progress progress-check hr-db case-template case-from-xlsx e2e e2e-db run-api-e2e run-ui-e2e testset help install check check-fast test run-api run-ui data ingest eval baseline openapi client \
        db demo-reset live-run copilot-live up down audit corpus-audit corpus-harvest corpus-download corpus-import corpus-verify corpus-manual corpus-report corpus-dates corpus-status corpus-junk corpus-export corpus-ingest compose-dev compose-test compose-demo langfuse-env-check \
        langfuse-up langfuse-down ollama-pull backup restore eval-fast openapi-diff llm-probe retrieval-eval retrieval-ladder retrieval-pool retrieval-silver judge kappa release sbom pin-images

progress:  ## Regenerate PROGRESS.md from docs/progress/ (never edit PROGRESS.md by hand; README §12)
	uv run python scripts/progress.py

progress-check:  ## Fail if PROGRESS.md is stale or a progress entry is invalid
	uv run python scripts/progress.py --check

help:  ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install:  ## Sync the uv workspace (all members, dev group and extras such as rerank)
	uv sync --all-packages --all-extras

check:  ## ruff, ruff format, mypy --strict, pytest, bandit, PROGRESS.md check
	uv run ruff check .
	uv run python scripts/progress.py --check
	uv run ruff format --check .
	uv run mypy --strict $(PY_SRC)
	uv run pytest -q
	uv run python -m credassure.evaluation.check_corpus_refs
	uv run bandit -q -c pyproject.toml -r $(PY_SRC)
	uv run lint-imports

check-fast:  ## ruff + PROGRESS.md check + fast tests (used by the Claude stop hook)
	uv run ruff check .
	uv run python scripts/progress.py --check
	uv run pytest -q -m "not slow"

test:  ## Full test suite with coverage
	uv run pytest --cov=credassure --cov-report=term-missing

audit:  ## Dependency vulnerability audit (accepted advisories: docs/security/risk-register.md)
	uv run pip-audit --skip-editable \
		--ignore-vuln PYSEC-2026-311 --ignore-vuln PYSEC-2026-3813 \
		--ignore-vuln PYSEC-2026-3814 --ignore-vuln PYSEC-2026-3815

ollama-pull:  ## Download qwen3:8b and nomic-embed-text (ADR 0017; not part of make check)
	@if $(COMPOSE) --profile dev ps --status running --services 2>/dev/null | grep -qx ollama; then \
		$(COMPOSE) --profile dev exec ollama ollama pull qwen3:8b; \
		$(COMPOSE) --profile dev exec ollama ollama pull nomic-embed-text; \
	elif command -v ollama >/dev/null 2>&1; then \
		ollama pull qwen3:8b; \
		ollama pull nomic-embed-text; \
	else \
		echo "No Ollama found. Install it and run 'OLLAMA_CONTEXT_LENGTH=8192 ollama serve', or start 'make compose-dev'."; \
		exit 1; \
	fi

run-api:  ## FastAPI on :8000 (docs at /docs)
	$(DEMO_TENANT) uv run $(ENV_FILE) uvicorn credassure.gateway.main:app --factory --reload --port 8000

E2E_DB := var/case-e2e.db
# The guard runs first, in the environment the gateway will see, and refuses var/case.db (the demo database).
E2E_GUARD = CASE_DB=$(E2E_DB) uv run $(ENV_FILE) python scripts/e2e_guard.py

e2e-db:  ## Fresh migrated + seeded e2e database (var/case-e2e.db); refuses the demo database
	$(E2E_GUARD)
	rm -f $(E2E_DB) $(E2E_DB)-wal $(E2E_DB)-shm
	uv run python -m credassure.ledger.migrate upgrade case $(E2E_DB)
	CASE_DB=$(E2E_DB) uv run $(ENV_FILE) python -m credassure.gateway.seed

run-api-e2e:  ## E2E gateway on :8001 using var/case-e2e.db (CORS for :3001); refuses the demo database
	$(E2E_GUARD)
	CASE_DB=$(E2E_DB) UI_ORIGINS=http://localhost:3001 uv run $(ENV_FILE) uvicorn credassure.gateway.main:app --factory --port 8001

e2e:  ## Playwright on the isolated stack (explicit URLs win over any E2E_* in the env file); PW_ARGS="--project=u3"
	E2E_BASE_URL=http://localhost:3001 E2E_API_URL=http://localhost:8001 npm run e2e -w apps/web -- $(PW_ARGS)

run-ui-e2e:  ## E2E web dev server on :3001, talking to :8001
	NEXT_PUBLIC_API_BASE_URL=http://localhost:8001 NEXT_DIST_DIR=.next-e2e npm run dev -w apps/web -- -p 3001

openapi:  ## Export openapi.json (ADR 0004)
	uv run python -m credassure.gateway.openapi

openapi-diff:  ## Fail on a breaking openapi.json change against main (BASE=<ref> to override)
	uv run python scripts/openapi_diff.py $(or $(BASE),main)

client: openapi  ## Generate the TypeScript API client from openapi.json
	npm run generate -w packages/api-client

up: langfuse-env-check  ## Gateway, web, Ollama and Langfuse (dev profile)
	$(COMPOSE) --profile dev --profile langfuse up --build

down:  ## Stop the dev stack
	$(COMPOSE) --profile dev --profile langfuse down

backup:  ## Online backup of case.db, corpus.db, llm_cache.db to var/backups/<time>/
	deploy/scripts/backup.sh

release:  ## Release bundle var/release/v$(VERSION)/ (RELEASE.json, SBOM, eval reports): VERSION=1.0.0
	uv run python scripts/release.py --version "$(VERSION)"

sbom:  ## CycloneDX SBOM from uv.lock and package-lock.json -> var/release/sbom.cdx.json
	uv run python scripts/sbom.py

pin-images:  ## Pin Dockerfile and Compose images to registry digests (needs Docker + network); ARGS=--check
	uv run python scripts/pin_images.py $(ARGS)

restore:  ## Restore a backup: FROM=var/backups/<dir> (stop run-api first)
	deploy/scripts/restore.sh "$(FROM)"

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

run-ui:  ## Next.js dev server for the web app on http://localhost:3000
	npm run dev -w apps/web

data:  ## Seeded synthetic data -> data/frozen/v1 + hr.db (Phase 2, idempotent)
	uv run python -m credassure.datagen

hr-db:  ## Rebuild the gitignored hr.db from frozen hr/profiles.json (fresh clone, CI; allowed after G1)
	uv run python -m credassure.datagen hr-db

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

corpus-junk:  ## Flag homepages, menus, listings and contentless short pages as needs_review; list replacements
	uv run python -m credassure.datagen.harvest junk

corpus-export:  ## Write data/corpus/CORPUS_INDEX.md and .xlsx (one row per manifest entry + summary)
	uv run python -m credassure.datagen.harvest export

corpus-docker-%:  ## Run a corpus target in the hardened container, e.g. make corpus-docker-download (ADR 0020)
	$(COMPOSE) --profile tools run --rm corpus make corpus-$*

corpus-status:  ## One screen: real available vs 500, by source and owner; also regenerates CORPUS_INDEX.md/.xlsx
	uv run python -m credassure.datagen.harvest status

corpus-report:  ## Real corpus table: planned, available, manual pending, distance to 500
	uv run python -m credassure.datagen.harvest report

corpus-ingest: ingest  ## Alias so `make corpus-docker-ingest` runs Phase 7 ingestion in the container

ingest:  ## Index data/corpus + synthetic KFS/policies: corpus.db, FTS5, Chroma (Phase 7; re-runnable)
	uv run $(ENV_FILE) python -m credassure.retrieval.cli

retrieval-eval:  ## KR-05 recall@5/@10 for 3 retrievers x 3 chunkings x rerank -> evaluation/reports/retrieval-<date>.md
	uv run $(ENV_FILE) python -m credassure.evaluation.retrieval_eval

retrieval-ladder:  ## P4 ladder: RUNG=0..3 LABEL=.. [REWRITE=1] [RERANK=1]; CURVE=1 picks the dev-only threshold; REPORT=1 writes the report
	@if [ -n "$(CURVE)" ]; then uv run $(ENV_FILE) python -m credassure.evaluation.retrieval_ladder curve; \
	elif [ -n "$(REPORT)" ]; then uv run python -m credassure.evaluation.retrieval_ladder report; \
	else uv run $(ENV_FILE) python -m credassure.evaluation.retrieval_ladder run --rung $(RUNG) --label "$(LABEL)" $(if $(REWRITE),--rewrite) $(if $(RERANK),--rerank); fi

retrieval-pool:  ## Blind pooled top-5 of all 18 configs -> evaluation/retrieval/v1/judging/ (E8 M1)
	uv run $(ENV_FILE) python -m credassure.evaluation.retrieval_judging pool

retrieval-silver:  ## Silver labels: self-consistency gate, v1.1-silver strict/lenient + diff, human sample
	uv run python -m credassure.evaluation.retrieval_judging silver

JUDGE ?= pritish
SAMPLE ?= 1
judge:  ## Judge the blind human sample, one passage at a time, resumable (JUDGE=name; SAMPLE= for the whole pool)
	uv run $(ENV_FILE) python -m credassure.evaluation.retrieval_judging judge --judge $(JUDGE) $(if $(SAMPLE),--sample)

kappa:  ## Cohen's kappa, silver vs JUDGE on the human sample (run after make judge)
	uv run python -m credassure.evaluation.retrieval_judging kappa --judge $(JUDGE)

eval:  ## Run the 100 items through the API on the configured model (Phase 11/P7); ARGS="--ablation A1" | "--fake --only routing"
	APP_ENV=dev LOG_LEVEL=WARNING uv run $(ENV_FILE) python scripts/eval_harness.py $(ARGS)

eval-judge:  ## J1 grades the run's regulatory answers and writes a 20% human sample: RUN=var/eval/<run>
	uv run $(ENV_FILE) python -m credassure.evaluation.judge_j1 judge --run $(RUN)

eval-kappa:  ## Kappa between J1 and the labelled human sample (ADR 0014): RUN=var/eval/<run>
	uv run python -m credassure.evaluation.judge_j1 kappa --run $(RUN)

eval-report:  ## E13 report: RUN=var/eval/<run> ABL="var/eval/<run>-A1 ..." OUT=evaluation/reports/E13-<date>.md
	uv run python -m credassure.evaluation.eval_report --full $(RUN) --ablation $(ABL) --calibration $(RUN)/j1-calibration.json --out $(OUT)

load-smoke:  ## Scope #35: 10 concurrent demo cases through the API, p95 per stage (ARGS="--fake" for locking only)
	APP_ENV=dev LOG_LEVEL=WARNING uv run $(ENV_FILE) python scripts/load_smoke.py $(ARGS)

eval-ablations:  ## A1-A5 on the configured model, each on its affected categories only (ablations.yaml)
	for a in A1 A2 A3 A4 A5; do $(MAKE) eval ARGS="--ablation $$a"; done

# ponytail: offline subset; the API-driven fast eval subset replaces it with the Phase 11 harness
eval-fast:  ## Prompt change control (#36): version-bump check + offline prompt subset (FakeLLM)
	uv run python -m credassure.core.prompts check --base $${PROMPTS_BASE:-origin/main}
	uv run python -m credassure.guardrails.policy check
	uv run pytest -q packages/llm/tests agents/supervisor/tests/test_resilience.py tests/e2e

llm-probe:  ## Does the endpoint honour guided JSON? Decides LLM_SUPPORTS_GUIDED_JSON (ADR 0017)
	uv run $(ENV_FILE) python -m credassure.llm.probe

redteam:  ## K6 red-team log: 20 frozen prompts + 5 E14 probes through the API, verdicts by code (writes var/redteam/<run>/redteam.md); ARGS="--fake"
	APP_ENV=dev LOG_LEVEL=WARNING uv run $(ENV_FILE) python scripts/redteam_run.py $(ARGS)

rag-baseline:  ## RAG-only baseline: S1 prompt + copilot hybrid top-5, no agents, regulatory 25 (writes var/rag-only-baseline.jsonl)
	uv run $(ENV_FILE) python scripts/rag_only_baseline.py

baseline:  ## Prompt baselines S1-S3 on the 100 items (EVAL_BASE_URL / EVAL_MODEL; default local Ollama, ADR 0017)
	uv run $(ENV_FILE) python -m credassure.evaluation.baseline.run --strategy all

testset:  ## Rebuild evaluation/testset/v1 and the retrieval/red-team/fixture assets (refuses once frozen)
	uv run python -m credassure.evaluation.build_testset
	uv run python -m credassure.evaluation.build_assets

db:  ## Migrate var/case.db + var/corpus.db and seed users (needs SEED_PASSWORD; ADR 0005, scope #29)
	uv run python -m credassure.ledger.migrate upgrade case var/case.db
	uv run python -m credassure.ledger.migrate upgrade corpus var/corpus.db
	$(DEMO_TENANT) uv run $(ENV_FILE) python -m credassure.gateway.seed  # SEED_PASSWORD via Settings, into CASE_DB

live-run:  ## Live full-feature run on the configured model: every feature through the API (var/live-run/); see scripts/live_run.sh
	APP_ENV=dev LLM_ENABLED=true LOG_LEVEL=WARNING uv run $(ENV_FILE) python scripts/live_run.py $(ARGS)

copilot-live:  ## E8 live: the 44 copilot items through the API on the configured model (var/e8-live)
	uv run $(ENV_FILE) python scripts/copilot_live.py $(ARGS)

case-template:  ## Regenerate data/templates/case_template.xlsx and sample_case/ from the upload schemas
	uv run python scripts/case_xlsx.py template
	uv run python scripts/case_xlsx.py convert data/templates/case_template.xlsx data/templates/sample_case
	mkdir -p data/templates/sample_case/kfs
	cp data/frozen/v1/kfs/KFS-OF-01-[ABC]-v1.md data/frozen/v1/kfs/KFS-OF-01-[ABC]-v1-SCH.md data/templates/sample_case/kfs/

case-from-xlsx:  ## Filled template -> case CSV/JSON + offers, validated like an upload: FILE=... OUT=...
	@test -n "$(FILE)" -a -n "$(OUT)" || { echo "usage: make case-from-xlsx FILE=case.xlsx OUT=var/my_case"; exit 2; }
	uv run python scripts/case_xlsx.py convert "$(FILE)" "$(OUT)"

demo-reset:  ## Recreate the demo cases in var/case.db through the API (tenant demo; stop run-api first)
	$(DEMO_TENANT) uv run $(ENV_FILE) python scripts/demo_reset.py
