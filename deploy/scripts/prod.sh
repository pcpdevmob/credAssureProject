#!/usr/bin/env bash
# docker compose for the hosted deployment, from anywhere in the repo:
#   deploy/scripts/prod.sh up -d --build     start or update
#   deploy/scripts/prod.sh ps | logs -f gateway | restart gateway | down
# Reads DOMAIN (and the gateway's secrets) from the repo-root .env.
set -euo pipefail
cd "$(dirname "$0")/../.."
[ -f .env ] || { echo "no .env: copy deploy/env/server.env.example to .env and fill it in" >&2; exit 1; }
exec docker compose -f deploy/compose/production.yaml --env-file .env "$@"
