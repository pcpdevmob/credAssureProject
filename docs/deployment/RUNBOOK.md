# Runbook

Scope #45. One entry per incident: how it shows, what to do, how to confirm. Every command runs from the repo root.
Help for users: `docs/help/`. Error codes: `docs/help/error-messages.md`.

## Endpoint down
**Shows:** the web banner says the copilot is unavailable; `GET /v1/health/ready` → `checks.model` is `open` (circuit
breaker tripped after 5 failures, retried after 60 s); narratives fall back to templates.
**Do:**
1. `make llm-probe` — is the model answering at all?
2. Local model: `ollama ps`, then `ollama serve` / `make ollama-pull`. Course endpoint: check the VPN or CA path
   (`LLM_CA_CERT`) and the key in `.env` (never paste it anywhere).
3. During a demo, don't wait for it: restart the gateway with `REPLAY_MODE=true` (recorded replies, see Demo reset) or
   `LLM_ENABLED=false`. Gates, figures, routing and approval do not depend on the model.
**Confirm:** `checks.model` is `closed` (or `replay`).

## Quota exhausted
**Shows:** the quota banner at 70% / 90%; at 100% `checks.quota.level` is `exhausted` and `/health/ready` is `degraded`.
**Do:** stop evaluation runs first (`make eval`, ablations, `copilot-live` use the most tokens). Lower
`LLM_RATE_PER_MINUTE` if the course endpoint throttles. Finish the session with `REPLAY_MODE=true` or `LLM_ENABLED=false`.
**Confirm:** the banner clears after the quota window resets.

## Database locked
**Shows:** `database is locked` in the gateway log, or 409 `RUN_IN_PROGRESS` on a run.
**Do:**
1. One gateway per `var/case.db`: stop a second `make run-api`, an old `make live-run` or an open `sqlite3` shell.
2. A run that died keeps its lock row until three heartbeats are missed (90 s); the next run then proceeds.
3. Never delete `case.db-wal` while the gateway is running. If the file is corrupt, `make restore FROM=...`
   (`docs/deployment/backup-restore.md`).
**Confirm:** `GET /v1/health/ready` → `checks.db` is `ok`; a case run returns 202.

## Corpus missing
**Shows:** the copilot abstains on every question; `var/corpus.db` or `var/chroma/` is missing or empty.
**Do:** `make corpus-status` (what is available), then `make ingest`. Raw public files are never in git (L3/L4); get
them with `make corpus-download` or restore `corpus.db` from a backup.
**Confirm:** `make corpus-status` shows ≥ 500 real documents; a copilot question returns a cited answer.

## Demo reset
Before a rehearsal or the demo:
1. `make backup` (so the reset can be undone).
2. Stop `make run-api`, then `make demo-reset`: recreates the seeded cases, the blocked case and the happy-path case
   (CA-2026-0016) in tenant `demo` through the API.
3. Record replies for the fallback: run the demo once live with `LLM_CACHE_PATH` set (the default). Every model reply
   is now in `var/llm_cache.db`.
4. If the endpoint is slow on the day: restart with `REPLAY_MODE=true`. Recorded calls are answered from the cache; any
   other call falls back to templates. The endpoint is never called. `/v1/health/ready` shows `model: replay`.
5. Last resort: the recorded video (ADR 0015).
Script: `docs/demo/demo-script.md`.
