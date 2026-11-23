#!/usr/bin/env bash
# Online backup of the hosted case.db (cron from server-setup.sh; docs/deployment/azure.md §7).
# sqlite3 .backup is safe while the gateway writes (WAL). Keeps the newest $KEEP copies.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
KEEP="${KEEP:-7}"
SRC="$REPO/var/case.db"
DEST="$REPO/var/backups"
[ -f "$SRC" ] || { echo "$(date -Is) no $SRC yet"; exit 0; }
mkdir -p "$DEST"
out="$DEST/case-$(date +%Y%m%d-%H%M%S).db"
sqlite3 "$SRC" ".backup '$out'"
sqlite3 "$out" "PRAGMA integrity_check;" | grep -qx ok || { echo "$(date -Is) integrity check failed: $out"; exit 1; }
gzip "$out"
ls -1t "$DEST"/case-*.db.gz | tail -n +"$((KEEP + 1))" | xargs -r rm -f
echo "$(date -Is) backup ok: $out.gz"
