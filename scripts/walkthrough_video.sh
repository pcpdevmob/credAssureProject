#!/usr/bin/env bash
# make walkthrough-video: record the end-to-end walk-through (every role, every flow, Ask CredAssure) to a video.
# Starts the isolated e2e stack (fresh var/case-e2e.db, gateway :8001 with MODELS, web :3001), records with
# scripts/walkthrough_video.cjs, stops what it started, and converts to MP4 when ffmpeg is installed.
# Needs: .env with E2E_PASSWORD (12+ characters); for real copilot answers MODELS=local with Ollama running
# (qwen3:8b) and the search index (var/corpus.db, var/chroma-local-bge). Never touches var/case.db.
set -euo pipefail
cd "$(dirname "$0")/.."
MODELS=${MODELS:-local}
OUT=${OUT:-var/walkthrough/$(date -u +%Y%m%dT%H%M%SZ)}
mkdir -p "$OUT"
for port in 8001 3001; do
  if lsof -ti tcp:"$port" >/dev/null 2>&1; then echo "port $port is in use: stop the e2e stack first (make stop)"; exit 1; fi
done
if [ "$MODELS" = local ] && ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "note: Ollama is not answering on :11434, so Ask CredAssure will show its 'model unavailable' reply."
  echo "      Start it (ollama serve; ollama pull qwen3:8b) for real answers, or press Ctrl-C now."; sleep 5
fi
[ -f var/corpus.db ] || echo "note: var/corpus.db is missing: copilot answers about regulations will abstain (make ingest)."
make e2e-db
pids=()
cleanup() { for p in "${pids[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT
make run-api-e2e MODELS="$MODELS" >"$OUT/api.log" 2>&1 & pids+=($!)
make run-ui-e2e >"$OUT/web.log" 2>&1 & pids+=($!)
echo "starting the e2e stack (logs in $OUT)…"
for _ in $(seq 1 120); do
  curl -sf http://localhost:8001/v1/health/live >/dev/null 2>&1 && curl -sf -o /dev/null http://localhost:3001/login/ && break
  sleep 2
done
curl -sf http://localhost:3001/login/ >/dev/null || { echo "the e2e stack did not start; see $OUT/api.log and $OUT/web.log"; exit 1; }
node scripts/walkthrough_video.cjs "$OUT"
if command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg -loglevel error -y -i "$OUT/CredAssure_Walkthrough.webm" -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -movflags +faststart "$OUT/CredAssure_Walkthrough.mp4"
  echo "video: $OUT/CredAssure_Walkthrough.mp4"
else
  echo "video: $OUT/CredAssure_Walkthrough.webm (install ffmpeg for an MP4: brew install ffmpeg)"
fi
