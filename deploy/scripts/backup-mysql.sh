#!/bin/sh
# ADR 0039: consistent online dump of case.db on MySQL (the Compose `mysql` service), with the
# append-only triggers. Writes var/backups/mysql-<UTC time>.sql.gz (mode 600) and its SHA-256.
# Restore: gunzip -c <file> | docker compose ... exec -T mysql sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" credassure'
# then run the gateway once (migrations are idempotent) and check GET /v1/cases/{id}/audit verifies.
set -eu
cd "$(dirname "$0")/../.."
umask 077
mkdir -p var/backups
out="var/backups/mysql-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
docker compose -f deploy/compose/compose.yaml --profile mysql exec -T mysql sh -c \
  'mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" --single-transaction --triggers --hex-blob credassure' \
  | gzip > "$out"
sha256sum "$out" > "$out.sha256"
echo "$out"
