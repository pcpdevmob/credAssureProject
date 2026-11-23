#!/usr/bin/env bash
# Smoke test of a running CredAssure deployment, from any laptop (docs/deployment/azure.md §9).
#   SMOKE_USER=preparer.login SMOKE_PASSWORD='...' deploy/scripts/smoke.sh https://credassure.sharentest.com
# Read-only apart from one copilot question: it never creates, runs or approves a case.
# The user should be a preparer or evaluator (no MFA); approvers and admins need a TOTP code.
# Prints PASS/FAIL per step; exit code = number of failed steps. Needs curl and python3.
set -uo pipefail

BASE="${1:-${SMOKE_URL:-}}"
[ -n "$BASE" ] || { echo "usage: SMOKE_USER=... SMOKE_PASSWORD=... $0 https://host" >&2; exit 64; }
BASE="${BASE%/}"
fails=0
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

step() { # step NAME EXPECTED_STATUS CURL_ARGS...
  local name="$1" want="$2"
  shift 2
  local code
  code="$(curl -sS -o "$tmp/body" -w '%{http_code}' --max-time 120 "$@" 2>"$tmp/err")" || code="000"
  if [ "$code" = "$want" ]; then
    printf 'PASS  %-28s %s\n' "$name" "$code"
    return 0
  fi
  printf 'FAIL  %-28s got %s, want %s %s\n' "$name" "$code" "$want" "$(head -c 200 "$tmp/err")"
  fails=$((fails + 1))
  return 1
}

json() { python3 -c "import json,sys; d=json.load(open('$tmp/body')); print($1)" 2>/dev/null; }

step "https certificate" 200 "$BASE/" || true
step "web app (sign-in page)" 200 "$BASE/login" || true
step "gateway live" 200 "$BASE/v1/health/live" || true
if step "gateway ready" 200 "$BASE/v1/health/ready"; then
  echo "      status=$(json "d['status']") db=$(json "d['checks']['db']") model=$(json "d['checks']['model']")"
  [ "$(json "d['checks']['model']")" = "open" ] && echo "      WARN  model circuit open (course and fallback both down?)"
fi

if [ -z "${SMOKE_USER:-}" ] || [ -z "${SMOKE_PASSWORD:-}" ]; then
  echo "SKIP  sign-in steps (set SMOKE_USER and SMOKE_PASSWORD)"
else
  login="$(python3 -c 'import json,os; print(json.dumps({"username": os.environ["SMOKE_USER"], "password": os.environ["SMOKE_PASSWORD"]}))')"
  if step "sign in" 200 -H 'Content-Type: application/json' -d "$login" "$BASE/v1/auth/token"; then
    token="$(json "d['access_token']")"
    stage="$(json "d['stage']")"
    if [ "$stage" != "full" ]; then
      echo "FAIL  sign-in stage               '$stage' (use a preparer or evaluator without MFA or a temporary password)"
      fails=$((fails + 1))
    else
      auth=(-H "Authorization: Bearer $token")
      step "profile (/v1/me)" 200 "${auth[@]}" "$BASE/v1/me" || true
      if step "case list" 200 "${auth[@]}" "$BASE/v1/cases"; then
        echo "      cases visible: $(json "len(d['items'])")"
      fi
      q='{"message": "How do I start a new case?"}'
      if step "copilot question (model)" 200 "${auth[@]}" -H 'Content-Type: application/json' -d "$q" "$BASE/v1/copilot/chat"; then
        echo "      reply: $(json "str(d.get('answer') or d)[:120]")"
      fi
      step "sign out" 200 -X POST "${auth[@]}" "$BASE/v1/auth/logout" || true
    fi
  fi
fi

step "API docs not public" 404 "$BASE/docs" || true
echo
[ "$fails" -eq 0 ] && echo "ALL PASS" || echo "$fails step(s) FAILED"
exit "$fails"
