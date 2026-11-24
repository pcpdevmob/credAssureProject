# CredAssure — demo runbook

For the [demo script](demo-script.md). Use one laptop, the local model (Ollama qwen3:8b, ADR 0017) and the demo database `var/case.db` (tenant `demo`).
The recorded video and screenshots are the last fallback (ADR 0015).

## Pre-demo checklist (start 30 minutes before)

Do these in order. Each step depends on the one before it.

1. **Ollama at 8K, fully on the GPU**
   ```sh
   OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_KEEP_ALIVE=30m ollama serve     # menu-bar app: launchctl setenv, then restart it
   ollama run qwen3:8b "Reply OK" >/dev/null                         # load it
   ollama ps                                                         # expect qwen3:8b, CONTEXT 8192, 100% GPU
   ```
   If `ollama ps` shows a 4096 context or less than 100% GPU, close other GPU apps and restart Ollama (troubleshooting.md).
2. **Stop the API.** Stop `make run-api` (Ctrl-C) and confirm that `lsof -i :8000` prints nothing. demo-reset refuses to run while :8000 is busy.
3. **`make demo-reset`.** It backs up `var/case.db`, purges the demo cases (an audited purge, and the chain is re-verified), then drives 10 cases through the real API.
   With the live model this takes several minutes (it can wait up to 15 minutes per case). Check the table it prints:
   ```
   CA-2026-0016  AWAITING_APPROVAL  route=director_finance  …   ← main case
   CA-2026-0024  PAUSED             route=None  question='…min_cash_buffer…'   ← blocked case
   ```
   If either line differs, stop and fix it before the demo. The script also exits non-zero on any unexpected state.
4. **Start the API, then the UI** (two terminals):
   ```sh
   make run-api      # :8000, tenant demo
   make run-ui       # :3000 (CORS allows :3000 only)
   ```
5. **Health checks**
   ```sh
   curl -s localhost:8000/v1/health/live
   curl -s localhost:8000/v1/health/ready    # "status": "ok"; model check not "open"/"disabled"; quota level not "exhausted"
   ```
6. **Browser.** Set zoom to **125%** and hide bookmarks. Use **one browser profile (or one private window) per role**, because the token is held in memory only.
   - Window 1: `demo.preparer`, open CA-2026-0024 Workflow in one tab and CA-2026-0016 Funding in another.
   - Window 2: `demo.director`, open the **Approval inbox** (signed in with password + phone code).
   - Window 3: `demo.evaluator`, open CA-2026-0016 Audit, and `localhost:8000/docs` already **Authorize**d with an evaluator token.
   Each account has its own password (`var/initial-passwords.txt` or `SEED_PASSWORD_<USER>` in `.env`). Never show
   either file on screen.
7. **Warm the model.** In a throwaway preparer tab on a **different** demo case (for example CA-2026-0017), ask T007 once. This loads the model and caches embeddings.
   Do **not** click Negotiate or Approve on CA-2026-0016 during warm-up. Both are one-shot actions, and redoing them needs demo-reset.
8. **Ready state:** notifications off, the terminals out of view (keep one visible for the fallback), and this runbook open on a second screen.

## Fallback: model off mid-demo (`LLM_ENABLED=false`)

Use this if the model hangs or `/health/ready` shows the model circuit `open`. No reset is needed, because every stored fact, gate and route stays.

```sh
# in the API terminal: Ctrl-C, then
LLM_ENABLED=false make run-api      # an exported variable beats the env file
```
Reload the preparer window. **Sign in again:** the old token is still valid, but the page reload clears the in-memory token.

| Beat | With the model off |
|---|---|
| Sign-in, CA-2026-0024 pause | Same (code) |
| Funding, offers, provenance | Same figures, flags and ranking (code). The driver explanation is template text, not model wording |
| Negotiation | Same (no model in core) |
| Critic + routing | Same (code). Narratives are templates |
| Regenerate report (7:30) | Same (code): the report is rendered from ledger facts with templates |
| Copilot | "Unavailable" banner. **T020 abstains and T086 is refused exactly as before** (code). T007 now returns the abstention string. Say: "with the model off, the copilot never guesses. It abstains." Then show the E8 evidence slide line for the live cited answer |
| Director approval, audit | Same (code) |

Say: *"Everything that decides anything is still working. The model only reads and drafts."* (ARCHITECTURE Q5.)

## If a step hangs

- **Up to 20 seconds is normal** for a model call (the KFS reading is the slowest). Fill the time: "the model is the only slow part; gates are code."
- **Over 20 seconds:** move on to the next beat and come back, or show the matching screenshot or video segment.
- **A run or stage hangs:** the 30 s model timeout and 5 min stage timeout end it with the template fallback. Do not wait for it on stage.
  Switch to the `LLM_ENABLED=false` fallback above.
- **Copilot spins:** ask the next planned question. If none answers, go to the fallback.
- **Negotiate returns 409:** the round was already sent (one per case). Show the stored message and the revised offer instead.
- **Approve returns 409 `REPORT_STALE` ("report stale, regenerate"):** the 7:30 beat was skipped. Switch to `demo.preparer` → Review →
  **Regenerate report**, then approve again as the Director. Reject and return are never blocked by it.
- **A "sign in again" screen or a 401:** sign in again in that window. Tokens are short-lived and held in memory.
- **The UI shows "Cannot reach the CredAssure service":** the API has stopped. Restart `make run-api` and reload.
- **Never run `make demo-reset` during the demo.** It needs :8000 free, takes minutes and resets every demo case.

## After the demo
Leave `var/case.db` as it is (the approval is the audit evidence). Run `make demo-reset` again before the next rehearsal.
