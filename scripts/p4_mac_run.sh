#!/usr/bin/env bash
# P4 Mac run (docs/plan/P4-mac-runbook.md): ladder rungs 0-3 and the dev-only answerability curve.
# Run from the repo root on feature/copilot-p4:  bash scripts/p4_mac_run.sh
# Everything is logged to var/p4-run.log so progress can be followed from another session.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p var
LOG=var/p4-run.log
exec > >(tee -a "$LOG") 2>&1
step() { echo; echo "=== $(date '+%H:%M:%S') $* ==="; }

step "sync (keeps installed extras such as sentence-transformers)"
uv sync --all-packages --locked --inexact
cp -n var/corpus.db "var/corpus.db.bak-p4" || true   # rollback point for the re-ingest

step "rung 0: current index"
make retrieval-ladder RUNG=0 LABEL=baseline
step "re-ingest with contextual headers (chunk ids and text unchanged)"
RETRIEVAL_CONTEXT_HEADERS=true make ingest
step "rung 1: headers"
RETRIEVAL_CONTEXT_HEADERS=true make retrieval-ladder RUNG=1 LABEL=headers
step "rung 2: headers + glossary rewrite"
RETRIEVAL_CONTEXT_HEADERS=true make retrieval-ladder RUNG=2 LABEL=headers+glossary REWRITE=1
step "rung 3: headers + glossary + reranker"
RETRIEVAL_CONTEXT_HEADERS=true make retrieval-ladder RUNG=3 LABEL=headers+glossary+rerank REWRITE=1 RERANK=1
step "answerability curve (dev split only)"
RETRIEVAL_QUERY_REWRITE=true make retrieval-ladder CURVE=1
step "report"
make retrieval-ladder REPORT=1
step "P4_DONE"
