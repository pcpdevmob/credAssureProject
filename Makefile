.DEFAULT_GOAL := help
PY_SRC := apps/gateway/src packages/observability/src
COMPOSE := docker compose -f deploy/compose/compose.yaml

.PHONY: help install check check-fast test run-api run-ui data ingest eval baseline openapi demo-reset \
        audit compose-dev compose-test compose-demo langfuse-env-check langfuse-up langfuse-down

help:  ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install:  ## Sync the uv workspace (all members + dev group)
	uv sync --all-packages

check:  ## ruff, ruff format, mypy --strict, pytest, bandit
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy --strict $(PY_SRC)
	uv run pytest -q
	uv run bandit -q -c pyproject.toml -r $(PY_SRC)

check-fast:  ## ruff + fast tests (used by the Claude stop hook)
	uv run ruff check .
	uv run pytest -q -m "not slow"

test:  ## Full test suite with coverage
	uv run pytest --cov=credassure --cov-report=term-missing

audit:  ## Dependency vulnerability audit
	uv run pip-audit --skip-editable

run-api:  ## FastAPI on :8000 (docs at /docs)
	uv run uvicorn credassure.gateway.main:app --factory --reload --port 8000

openapi:  ## Export openapi.json (ADR 0004)
	uv run python -m credassure.gateway.openapi

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

run-ui:  ## React web app (apps/web, UI phase U0)
	@echo "run-ui: apps/web is built in UI phase U0 (CLAUDE_CODE_UI_PROMPT.md)"; exit 1

data:  ## Seeded synthetic data -> data/frozen/v1 (Phase 2)
	@echo "data: not implemented until Phase 2"; exit 1

ingest:  ## Download, hash and index the corpus (Phase 7)
	@echo "ingest: not implemented until Phase 7"; exit 1

eval:  ## Run the 100-item test set through the API (Phase 11)
	@echo "eval: not implemented until Phase 11"; exit 1

baseline:  ## Prompt baselines S1-S3 (Phase 3)
	@echo "baseline: not implemented until Phase 3"; exit 1

demo-reset:  ## Reset demo data and replay cache (Phase 12)
	@echo "demo-reset: not implemented until Phase 12"; exit 1
