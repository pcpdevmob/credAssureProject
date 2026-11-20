#!/usr/bin/env bash
# Live full-feature run on the Mac (no demo mode): real model (Ollama qwen3:8b), real corpus and
# vector store, dev profile. Run from the repo root in your own Terminal:
#     bash scripts/live_run.sh                 # branch feature/LendWise (default)
#     BRANCH=feature/<other> bash scripts/live_run.sh
#     SKIP_UI=1 bash scripts/live_run.sh       # backend only
# Steps: update branch -> sync -> check Ollama -> API live run -> copilot-live (44 items) -> web UI
# Playwright suite on the isolated e2e stack. Never touches var/case.db (demo data).
# Everything is logged to var/live-run.log so progress can be followed from another session.
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p var
LOG=var/live-run.log
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1
step() { echo; echo "=== $(date '+%H:%M:%S') $* ==="; }
fail() { echo "LIVE_RUN_ABORTED: $*"; exit 1; }
BRANCH=${BRANCH:-feature/LendWise}
ENVS="--env-file deploy/env/models-local.env"
[ -f .env ] && ENVS="--env-file .env $ENVS"
export APP_ENV=dev LLM_ENABLED=true LOG_LEVEL=WARNING   # exported values beat the env files

step "branch $BRANCH"
git diff --quiet && git diff --cached --quiet || fail "tracked changes in the working tree; commit or stash them first"
git fetch origin || fail "git fetch failed"
git checkout "$BRANCH" || fail "checkout $BRANCH failed"
git pull --ff-only origin "$BRANCH" || fail "pull failed"
git log --oneline -1

step "sync (keeps installed extras such as sentence-transformers)"
uv sync --all-packages --locked --inexact || fail "uv sync failed"

step "Ollama"
curl -sf http://localhost:11434/api/tags | grep -q '"qwen3:8b"' \
  || fail "Ollama is not serving qwen3:8b: run 'OLLAMA_CONTEXT_LENGTH=8192 ollama serve' and 'make ollama-pull'"
echo "qwen3:8b available"
[ -f var/corpus.db ] || fail "var/corpus.db missing: run make ingest first"

step "1/3 live API run: every feature on the real model (throwaway DB under var/live-run/)"
uv run $ENVS python scripts/live_run.py
API_RC=$?

step "2/3 copilot-live: 44 frozen copilot items on the real model (var/e8-live)"
uv run $ENVS python scripts/copilot_live.py
CP_RC=$?

UI_RC=skipped
if [ "${SKIP_UI:-0}" != "1" ]; then
  step "3/3 web UI: Playwright on the isolated e2e stack (:8001 API, :3001 web), live model"
  if [ ! -d node_modules ]; then npm ci || fail "npm ci failed"; fi
  npx --yes playwright install chromium >/dev/null 2>&1 || true
  make e2e-db || fail "make e2e-db failed"
  make run-api-e2e > var/live-run-api.log 2>&1 & API_PID=$!
  make run-ui-e2e > var/live-run-ui.log 2>&1 & UI_PID=$!
  trap 'kill $API_PID $UI_PID 2>/dev/null; pkill -f "uvicorn credassure.gateway.main:app --factory --port 8001" 2>/dev/null; pkill -f "next dev.*-p 3001" 2>/dev/null' EXIT
  for i in $(seq 1 90); do
    curl -sf http://localhost:8001/v1/health/live >/dev/null && curl -sf -o /dev/null http://localhost:3001 && break
    sleep 2
  done
  # SEED_PASSWORD comes from .env inside uv run; this script never reads or prints it.
  uv run $ENVS make e2e
  UI_RC=$?
fi

step "summary"
echo "api live run rc=$API_RC (report: newest var/live-run/*/report.md)"
echo "copilot-live rc=$CP_RC (var/e8-live)"
echo "web UI rc=$UI_RC"
ls -1d var/live-run/*/ 2>/dev/null | tail -1
echo "LIVE_RUN_DONE"
