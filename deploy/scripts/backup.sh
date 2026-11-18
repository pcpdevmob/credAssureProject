#!/bin/sh
# Online SQLite backup of case.db, corpus.db and llm_cache.db (scope #38). See docs/deployment/backup-restore.md.
set -eu
cd "$(dirname "$0")/../.."
exec uv run python scripts/backup_db.py backup "$@"
