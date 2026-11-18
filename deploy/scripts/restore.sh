#!/bin/sh
# Restore a backup folder (stop the gateway first). Usage: deploy/scripts/restore.sh var/backups/<dir>
set -eu
cd "$(dirname "$0")/../.."
[ $# -ge 1 ] || { echo "usage: make restore FROM=var/backups/<dir>" >&2; exit 2; }
exec uv run python scripts/backup_db.py restore --from "$1"
