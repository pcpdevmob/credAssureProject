# Troubleshooting

## Startup fails
| Symptom | Cause | Fix |
|---|---|---|
| API exits on startup | `JWT_SECRET` missing or shorter than 32 characters; or `LLM_BASE_URL` unset while `LLM_ENABLED=true` | Set them in `.env` (see [environment.md](environment.md)), or `LLM_ENABLED=false` |
| `ModuleNotFoundError: credassure.agents…` | A bare `uv sync` removed workspace members | `make install` |
| `make check` fails right after `uv sync` | Same | `make install` |
| Copilot start fails: `No module named 'sentence_transformers'` | Installed without the `rerank` extra (bare `uv sync`) | `make install` (it adds every extra); never a bare `uv sync` |
| `make db` or `make demo-reset` fails: seed password | `SEED_PASSWORD` missing or under 12 characters | Set it in `.env` |
| `make demo-reset` refuses, or "database locked" | A gateway is running on :8000 | Stop `make run-api`, then retry |
| `make demo-reset` or `make e2e-db` refuses | Guard against the wrong database | Use the make target; it sets the right `CASE_DB` and `TENANT_ID` |
| Demo cases show e2e leftovers | e2e ran against the demo database | Stop the API → `make demo-reset` → restart |
| UI sign-in fails with a CORS error | UI on a port the API doesn't allow | Use :3000 or :5173, or add the origin to `UI_ORIGINS` |
| UI calls fail with 401 after a restart | Token signed with an old `JWT_SECRET` | Sign out and in again |
| UI type errors after an API change | Client out of date | `make openapi && make client` |
| Copilot always answers "I can't verify that…" | Model is off, or no index for the current `MODELS` | Start the model; run `make ingest` with the same `MODELS` |

## Ollama
| Symptom | Fix |
|---|---|
| `ollama ps` shows a 4096 context | Start with `OLLAMA_CONTEXT_LENGTH=8192 ollama serve` (menu-bar app: `launchctl setenv`, then restart it) |
| Explanations take 17–65 s | Thinking is on. Use `MODELS=local` (turns it off with `reasoning_effort`) and restart the API |
| `bind: address already in use :11434` | `killall Ollama; pkill -f "ollama serve"; pkill -f "ollama runner"`; `lsof -i :11434` should print nothing; start again |
| Model not found | `make ollama-pull` (or `make compose-dev` first if you use the container) |
| Slow, or not fully on the GPU | `ollama ps` should say 100% GPU; close other apps, keep the context at 8192 |
| Course endpoint errors | `make llm-probe MODELS=course`; check keys and CA paths in `.env`; the limit is about 55 requests a minute |

## Langfuse
| Symptom | Fix |
|---|---|
| `make langfuse-up` says `deploy/env/langfuse.env` is missing or has CHANGEME | Copy `langfuse.env.example` to `langfuse.env` and replace every CHANGEME |
| Web app and Langfuse both want :3000 | Run the UI on 5173: `npm run dev -w apps/web -- -p 5173` |
| No traces appear | Check `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` in `.env` and `TRACING_ENABLED=true`. To run without tracing, set `TRACING_ENABLED=false` |

## Corpus
| Symptom | Fix |
|---|---|
| Harvester stops on a host | A 403, 429 or challenge page. Expected: download those by hand (`data/corpus/MANUAL_DOWNLOADS.md`); don't work around it |
| `make corpus-import` rejects a PDF | Scanned PDF with no text layer; use the replacement listed in `MANUAL_DOWNLOADS.md` |
| `/offers` shows an old comparison | Offers re-uploaded but the stage wasn't re-run; re-run the LendWise stage |
