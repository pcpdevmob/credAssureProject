#!/usr/bin/env bash
# One command to run CredAssure locally with everything it needs: `make start` (or bash scripts/start.sh).
#
#   make start                          # course endpoint (Qwen3-8B), API, web, Langfuse if set up
#   make start MODELS=local             # local Ollama qwen3:8b instead (the evaluated model, ADR 0036)
#   make start MODELS=hf                # Hugging Face -> Featherless (token in .env)
#   make start ARGS="--no-model"        # no model at all (LLM_ENABLED=false): gates, figures, routing still work
#   make start ARGS="--no-langfuse"     # skip tracing
#   make stop                           # stop what `make start` started (also after a closed terminal)
#
# Order: tools -> .env present -> install if missing -> HR store, database and users -> model -> Langfuse
# -> API (waits for /v1/health/ready) -> web -> URLs. No demo cases are created.
# Ctrl-C stops the API, the web app and an Ollama it started; Langfuse keeps running (make langfuse-down).
# Logs and process ids go to var/start/. Settings are what `make run-api MODELS=<profile>` loads (.env, then
# deploy/env/models-<profile>.env). Only make start defaults to course; run-api and eval keep MODELS=local.
# This script never reads or prints .env: it only checks that the file exists; the API refuses to start
# without JWT_SECRET, and the users' password is the SEED_PASSWORD you set there.
# macOS bash 3.2 compatible (no associative arrays).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)
RUN=var/start
mkdir -p "$RUN"

MODELS=${MODELS:-course}
NO_MODEL=0 NO_LANGFUSE=0 NO_UI=0 FORCE_INSTALL=0
API_PORT=8000

say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok() { printf '   ok    %s\n' "$*"; }
warn() { printf '   note  %s\n' "$*"; }
die() { printf '\n   STOP  %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
up() { curl -sf -o /dev/null --max-time 2 "$1"; }
wait_for() {  # url, seconds
  local i=0
  while [ "$i" -lt "$2" ]; do
    up "$1" && return 0
    sleep 1
    i=$((i + 1))
  done
  return 1
}

stop_pidfile() {  # kill the process group recorded in var/start/<name>.pid
  local f="$RUN/$1.pid" pid
  [ -f "$f" ] || return 0
  pid=$(cat "$f")
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null
    sleep 1
    kill -KILL -- "-$pid" 2>/dev/null || true
    echo "   stopped $1"
  fi
  rm -f "$f"
}

stop_all() {
  stop_pidfile web
  stop_pidfile api
  stop_pidfile ollama
}

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; }

for arg in "$@"; do
  case "$arg" in
    stop) say "Stopping"; stop_all; echo "   Langfuse keeps running: make langfuse-down"; exit 0 ;;
    --no-model) NO_MODEL=1 ;;
    --no-langfuse) NO_LANGFUSE=1 ;;
    --no-ui) NO_UI=1 ;;
    --install) FORCE_INSTALL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage; die "unknown option $arg" ;;
  esac
done
MODELS_FILE=deploy/env/models-$MODELS.env
[ -f "$MODELS_FILE" ] || die "MODELS=$MODELS: no $MODELS_FILE (use local, course or hf)"
mk() { make --no-print-directory MODELS="$MODELS" "$@"; }

# ---- 1. tools and .env ----------------------------------------------------------------------------
say "1/7 Tools"
for t in uv make curl; do have "$t" || die "$t is not installed (docs/setup/prerequisites.md)"; done
[ "$NO_UI" = 1 ] || have npm || die "npm is not installed (Node 20+); or run with --no-ui"
ok "uv, make, curl$([ "$NO_UI" = 1 ] || echo ', npm')"
[ -f .env ] || die ".env is missing: cp .env.example .env, then set JWT_SECRET (32+ chars) and SEED_PASSWORD (12+ chars)"
ok ".env present (not read here)"
if up "http://localhost:$API_PORT/v1/health/live"; then
  die "an API already answers on :$API_PORT. Stop it (make stop, or Ctrl-C in its terminal) and run again"
fi

# ---- 2. install ---------------------------------------------------------------------------------
say "2/7 Install"
if [ "$FORCE_INSTALL" = 1 ] || [ ! -d .venv ]; then
  mk install || die "make install failed"
else
  ok "Python workspace installed (make start ARGS=--install to re-sync after a pull)"
fi
if [ "$NO_UI" = 0 ]; then
  if [ "$FORCE_INSTALL" = 1 ] || [ ! -d node_modules ]; then npm ci || die "npm ci failed"; else ok "node_modules present"; fi
fi

# ---- 3. data --------------------------------------------------------------------------------------
say "3/7 Data"
[ -f data/frozen/v1/hr.db ] || { mk hr-db || die "make hr-db failed"; }
ok "HR store data/frozen/v1/hr.db"
if [ -f var/case.db ]; then
  ok "database var/case.db"
else
  mk db > "$RUN/db.log" 2>&1 || die "make db failed: see $RUN/db.log (SEED_PASSWORD must be set in .env)"
  ok "database var/case.db created with the users (no cases)"
fi
CHROMA=$(sed -n 's/^CHROMA_PATH=//p' "$MODELS_FILE" | tail -1)
if [ -f var/corpus.db ] && [ -n "$CHROMA" ] && [ -d "$CHROMA" ]; then
  ok "search index var/corpus.db + $CHROMA"
else
  warn "search index missing (var/corpus.db or ${CHROMA:-the vector index}): the copilot will abstain on"
  warn "regulation questions. Unzip the team corpus share, then: make ingest MODELS=$MODELS"
fi

# ---- 4. model -------------------------------------------------------------------------------------
say "4/7 Model ($MODELS)"
if [ "$NO_MODEL" = 1 ]; then
  export LLM_ENABLED=false  # an exported value beats the env files
  ok "model off: gates, calculations, routing and approval work; narratives use templates"
elif [ "$MODELS" = local ]; then
  have ollama || die "Ollama is not installed (https://ollama.com), or run with --no-model"
  if up http://localhost:11434/api/tags; then
    ok "Ollama already running"
    warn "it must have been started with OLLAMA_CONTEXT_LENGTH=8192 (see CONTEXT in the table below)"
  else
    (set -m; OLLAMA_CONTEXT_LENGTH=8192 nohup ollama serve > "$RUN/ollama.log" 2>&1 & echo $! > "$RUN/ollama.pid")
    wait_for http://localhost:11434/api/tags 30 || die "Ollama did not start: see $RUN/ollama.log"
    ok "Ollama started with OLLAMA_CONTEXT_LENGTH=8192"
  fi
  curl -sf http://localhost:11434/api/tags | grep -q '"qwen3:8b"' || { ollama pull qwen3:8b || die "ollama pull qwen3:8b failed"; }
  echo "   loading qwen3:8b (the first answer takes longer otherwise)"
  ollama run qwen3:8b "hi" > /dev/null 2>&1 || die "qwen3:8b did not answer: see $RUN/ollama.log"
  ollama ps | sed 's/^/   /'
else
  # Reachability only: no key is sent. Exit 0, or 60 (the server answered with a certificate curl's own
  # store does not trust: the course CA, which the API loads from LLM_CA_CERT), means the host answered;
  # 6, 7 and 28 mean it did not. Anything else (a proxy in the way, say) is reported as unconfirmed.
  sed -nE 's/^(LLM|EMBED)_BASE_URL=(https:.*)$/\2/p' "$MODELS_FILE" | while read -r url; do
    curl -s -o /dev/null --connect-timeout 5 --max-time 8 "$url/models"
    rc=$?
    case $rc in
      0 | 60) ok "$url answers" ;;
      6 | 7 | 28) warn "$url does not answer: connect the course VPN, or run make start MODELS=local" ;;
      *) warn "$url could not be confirmed (curl exit $rc); the API reports the model on /v1/health/ready" ;;
    esac
  done
  warn "keys and the CA file come from .env (LLM_API_KEY, EMBED_API_KEY, LLM_CA_CERT)"
fi

# ---- 5. Langfuse ----------------------------------------------------------------------------------
say "5/7 Tracing (Langfuse)"
UI_PORT=3000
if [ "$NO_LANGFUSE" = 1 ]; then
  export TRACING_ENABLED=false
  ok "tracing off (--no-langfuse)"
elif up http://localhost:3000/api/public/health; then
  UI_PORT=5173
  ok "Langfuse already running on http://localhost:3000"
elif have docker && docker info > /dev/null 2>&1 && [ -f deploy/env/langfuse.env ] \
  && ! grep -q CHANGEME deploy/env/langfuse.env; then
  mk langfuse-up > "$RUN/langfuse.log" 2>&1 || die "make langfuse-up failed: see $RUN/langfuse.log"
  if wait_for http://localhost:3000/api/public/health 120; then
    UI_PORT=5173
    ok "Langfuse on http://localhost:3000 (web app moves to :5173)"
  else
    die "Langfuse did not answer within 2 minutes: see $RUN/langfuse.log (or run with --no-langfuse)"
  fi
else
  export TRACING_ENABLED=false
  warn "tracing off: Docker is not running or deploy/env/langfuse.env is not set up (README §7 Tracing)"
fi

# ---- 6. API ---------------------------------------------------------------------------------------
say "6/7 API"
trap 'echo; say "Stopping"; stop_all; echo "   Langfuse keeps running: make langfuse-down"; exit 0' INT TERM
(set -m; nohup make --no-print-directory MODELS="$MODELS" run-api > "$RUN/api.log" 2>&1 & echo $! > "$RUN/api.pid")
api_up() {  # the reloader stays alive when the app fails to import, so watch the log too
  local i=0
  while [ "$i" -lt 120 ]; do
    up "http://localhost:$API_PORT/v1/health/live" && return 0
    grep -q "Traceback" "$RUN/api.log" 2>/dev/null && return 1
    sleep 1
    i=$((i + 1))
  done
  return 1
}
if ! api_up; then
  # last lines of the error, without pydantic's input_value (it could hold a value from .env)
  grep -v "input_value" "$RUN/api.log" | tail -n 12 | sed 's/^/   | /'
  stop_all
  die "the API did not start: see $RUN/api.log (a missing JWT_SECRET or SEED_PASSWORD in .env is the usual cause)"
fi
READY=$(curl -s --max-time 10 "http://localhost:$API_PORT/v1/health/ready" || true)
ok "API on http://localhost:$API_PORT (Swagger /docs)"
echo "   ready: $READY" | cut -c1-200

# ---- 7. web ---------------------------------------------------------------------------------------
say "7/7 Web app"
if [ "$NO_UI" = 1 ]; then
  ok "skipped (--no-ui)"
else
  up "http://localhost:$UI_PORT" && { stop_all; die "something already answers on :$UI_PORT; stop it and run again"; }
  (set -m; NEXT_PUBLIC_API_BASE_URL="http://localhost:$API_PORT" nohup npm run dev -w apps/web -- -p "$UI_PORT" \
    > "$RUN/web.log" 2>&1 & echo $! > "$RUN/web.pid")
  if wait_for "http://localhost:$UI_PORT" 120; then
    ok "web app on http://localhost:$UI_PORT"
  else
    warn "the web app is not answering yet: see $RUN/web.log"
  fi
fi

say "CredAssure is running"
[ "$NO_UI" = 1 ] || echo "   Web app   http://localhost:$UI_PORT   (users demo.preparer, demo.director, demo.vp, demo.evaluator,"
[ "$NO_UI" = 1 ] || echo "                                         password SEED_PASSWORD; MFA users enrol on first sign-in)"
echo "   API       http://localhost:$API_PORT/docs"
[ "${TRACING_ENABLED:-true}" = false ] || echo "   Langfuse  http://localhost:3000"
echo "   Model     $MODELS$([ "$NO_MODEL" = 1 ] && echo ' (off)')"
echo "   Logs      $ROOT/$RUN/{api,web,ollama,langfuse,db}.log"
echo "   Stop      Ctrl-C here, or make stop from another terminal"
while :; do
  sleep 5
  if [ ! -f "$RUN/api.pid" ]; then
    say "Stopped from another terminal (make stop)"
    exit 0
  fi
  if ! kill -0 "$(cat "$RUN/api.pid")" 2>/dev/null; then
    say "The API stopped (see $RUN/api.log)"
    stop_all
    exit 1
  fi
done
