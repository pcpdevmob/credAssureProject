# Environment variables

Source of truth: `apps/gateway/src/credassure/gateway/settings.py`; every value is validated at startup.
Template: `.env.example` (copy to `.env`; never commit it). `make` loads `.env`, then `deploy/env/models-$(MODELS).env`,
so the model profile wins for model settings. `MODELS` itself is a make variable, not an `.env` key.

## Required
| Variable | Used by | Meaning |
|---|---|---|
| `JWT_SECRET` | gateway | Signs login tokens; 32+ characters. The API won't start without it (outside `APP_ENV=test`) |
| `SEED_PASSWORD` | `make db`, `make demo-reset` | 12+ characters; password of every seeded user. `SEED_PASSWORD_<USERNAME>` overrides one user |
| `LLM_BASE_URL` | gateway | Required while `LLM_ENABLED=true`; the profile file sets it |
| `CORPUS_CONTACT_EMAIL` | `make corpus-harvest`, `make corpus-download` | Optional. Adds `; contact: <email>` to the scripted User-Agent (ADR 0020). Takes precedence over `CORPUS_CONTACT_URL`. If set but not a valid address, the commands stop. Set it in `.env`; never hard-code it. |
| `CORPUS_CONTACT_URL` | same | Optional. Used when no email is set: adds `; +<url>` (http or https). With neither set, the User-Agent is `CredAssure-capstone/1.0 (IIT KGP academic project)`. |

## App
| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | `dev` | `dev`, `test` or `demo`. `test` relaxes only the required-secret checks |
| `LOG_LEVEL` | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `TENANT_ID` | `default` | Tenant of this gateway process. `make run-api`, `make db` and `make demo-reset` set `demo` (the dev/demo database `var/case.db`); an exported value wins over `--env-file` |
| `CASE_DB` | `var/case.db` | Case, ledger and audit database. The e2e targets point it at `var/case-e2e.db` |
| `UI_ORIGINS` | `http://localhost:3000,http://localhost:5173` | CORS allowlist, comma-separated |
| `JWT_EXPIRY_MINUTES` | 30 | Token lifetime (max 30) |
| `RATE_LIMIT` | `120/minute` | Per user, else per client IP (NFR-04) |
| `MAX_UPLOAD_BYTES` | 2 MB | Upload cap (UI-02) |

## Model
| Variable | Default | Meaning |
|---|---|---|
| `LLM_ENABLED` | `true` | `false` runs every gate with template narratives; `LLM_BASE_URL` is then not required |
| `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` | profile | OpenAI-compatible chat endpoint. Local: Ollama `qwen3:8b`; course: `Qwen/Qwen3-8B` |
| `LLM_CA_CERT`, `EMBED_CA_CERT` | unset | Absolute path to the course CA file; must exist |
| `LLM_CONTEXT_TOKENS` | 8192 | Prompt sizing |
| `LLM_MAX_TOKENS` | 1024 | Output cap per call (max 1024) |
| `LLM_DISABLE_THINKING` | `false` (profiles set `true`) | Turn off Qwen3 thinking |
| `LLM_THINKING_SWITCH` | profile | `reasoning_effort` (Ollama) or `chat_template_kwargs` (vLLM) |
| `LLM_SUPPORTS_GUIDED_JSON` | `false` | Set `true` only after `make llm-probe` confirms it |
| `LLM_CALL_TIMEOUT_S` / `STAGE_TIMEOUT_S` | 30 / 300 | Per model call / per stage |
| `LLM_MAX_RETRIES` | 2 | Transient errors only (max 2) |
| `LLM_CIRCUIT_FAILURES` / `LLM_CIRCUIT_OPEN_S` | 5 / 60 | Circuit breaker, then template fallbacks |
| `LLM_RATE_PER_MINUTE` | 60 | Shared limiter (profiles: local 600, course 55) |
| `LLM_CACHE_PATH` | `var/llm_cache.db` | Response cache; empty turns it off |
| `TOKEN_QUOTA` | 2,000,000 | Team quota; warnings at 70% and 90% |
| `EVAL_BASE_URL`, `EVAL_MODEL`, `EVAL_API_KEY`, `EVAL_MAX_TOKENS`, `EVAL_NUM_CTX` | profile | Model used by baselines and evaluation scripts |

## Retrieval and copilot
| Variable | Default | Meaning |
|---|---|---|
| `EMBED_BASE_URL` | profile | `local` = in-process bge-small; otherwise an OpenAI-compatible embeddings endpoint |
| `EMBED_MODEL`, `EMBED_API_KEY`, `EMBED_BATCH`, `EMBED_RATE_PER_MINUTE`, `EMBED_CACHE_PATH` | profile | Embeddings client |
| `CORPUS_DB` | `var/corpus.db` | Corpus and FTS5 index; the Critic opens it read-only |
| `CHROMA_PATH` | `var/chroma` (profiles: `var/chroma-local-bge`, `var/chroma-course-bge`) | Vector store directory. The copilot uses the same store and `EMBED_*` embedder as `make ingest` |
| `COPILOT_SEARCH_MODE` | `hybrid` | `hybrid` (BM25 + dense, RRF) or `keyword` (BM25 only; tests, or no vector store) |
| `RERANKER` | `none` | `none`, `local_cross_encoder`, `llm_pointwise` (ADR 0013) |
| `RERANKER_MODEL`, `RERANKER_REVISION` | `BAAI/bge-reranker-base`, pinned | Cross-encoder (needs the `rerank` extra) |

## Tracing
| Variable | Default | Meaning |
|---|---|---|
| `TRACING_ENABLED` | `true` | Langfuse tracing; the PII mask always applies |
| `LANGFUSE_HOST` | `http://localhost:3000` | Self-hosted Langfuse (ADR 0016) |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | unset | From your Langfuse project. Langfuse's own secrets live in `deploy/env/langfuse.env` |

## Business rules and switches
| Variable | Default | Meaning |
|---|---|---|
| `BOUNDARY_RULE` | `hold` | Exactly ₹1.5 crore: `hold`, `director` or `vp` (APR-03) |
| `APPROVAL_THRESHOLD_PAISE` | 1,500,000,000 | ₹1.5 crore in paise |
| `GST_RATE` | 0.18 | GST on fees, never on interest |
| `APR_CONVENTION` | `nominal` | `nominal` or `effective` (ADR 0012) |
| `FORECAST_WEEKS` | 26 | Cash-flow horizon |
| `AGENT_MAX_STEPS` / `TOKEN_CAP_PER_STAGE` | 10 / 6000 | Per-invocation caps (SUP-07) |
| `AS_OF_DATE` | 2026-11-15 | Fixed "today" so results reproduce |
| `CREDASSURE_SEED` | 20261026 | Seed for the data generators |
| `PLANNER_MODE` | `fixed` | `fixed` or `llm_proposes` (code validates) |
| `FEATURE_STRETCH` | `false` | BRD §4.2 stretch items |
| `ABLATION` | unset | A1 to A5; evaluation only |

## End-to-end tests
`E2E_USERNAME`, `E2E_PASSWORD`, `E2E_BASE_URL`, `E2E_API_URL`: read by Playwright. The `make e2e*` targets set the URLs themselves, so don't put `E2E_*` URLs in `.env`.
