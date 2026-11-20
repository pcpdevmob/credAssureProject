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
| `CASE_DATABASE_URL` | unset | ADR 0039: `mysql+pymysql://user:pass@host/db` puts case.db on MySQL 8 (database collation `utf8mb4_bin`). Unset = SQLite at `CASE_DB` |
| `CHECKPOINT_DB` | `var/checkpoints.db` | LangGraph checkpoints when case.db is on MySQL (inside case.db on SQLite) |
| `UI_ORIGINS` | `http://localhost:3000,http://localhost:5173` | CORS allowlist, comma-separated |
| `JWT_EXPIRY_MINUTES` | 30 | Token lifetime (max 30) |
| `JWT_SESSION_MAX_MINUTES` | 240 | `POST /v1/auth/refresh` renews a token until this long after sign-in (max 720), then the user signs in again |
| `MFA_ENCRYPTION_KEY` | unset | ADR 0038: base64 of 32 random bytes; seals each TOTP secret at rest. Required while MFA is enforced (the API won't start without it) |
| `MFA_REQUIRED_ROLES` | `director_finance,vp_finance,user_admin` | Roles that must enrol a TOTP app before their first full sign-in |
| `MFA_ENFORCED` | on outside `APP_ENV=test` | `false` turns the second factor off (the evaluation scripts and the demo profile do this for the seeded users) |
| `BOOTSTRAP_ADMIN_PASSWORD` | unset | Read once by `make admin NAME=<username>` to create the first `user_admin` (changed at first sign-in) |
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
| `REPLAY_MODE` | `false` | Demo fallback (ADR 0015): answer only from replies recorded in `LLM_CACHE_PATH`; a miss falls back to templates and the chat endpoint is never called (embeddings still use their cache, then the endpoint) |
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
| `HELP_DIR` | `docs/help` | Product help the copilot cites (ADR 0035); indexed in memory at start |
| `COPILOT_MEMORY_MESSAGES` | `8` | Redacted messages per user and case replayed to the model (CP-11); `0` turns memory off |
| `RERANKER` | `none` | `none`, `local_cross_encoder`, `llm_pointwise` (ADR 0013) |
| `RERANKER_MODEL`, `RERANKER_REVISION` | `BAAI/bge-reranker-base`, pinned | Cross-encoder (needs the `rerank` extra) |
| `RETRIEVAL_CONTEXT_HEADERS` | `false` | Ingest only: embed section chunks with a "publisher · title · section · date" header; chunk text and ids unchanged; a toggle re-indexes (P4, scope #61) |
| `RETRIEVAL_QUERY_REWRITE` | `false` | Glossary expansion of the query before keyword and dense search (`config/glossary.yaml`, scope #62) |
| `RERANK_ORDER` | `true` | `false`: the reranker only scores (for the gate) and the hybrid order is kept; the P4 ladder chose this (dev recall@5 17/20 vs 11/20 reranked) |
| `SOURCE_PRIORITY` | `false` | `true`: the copilot reads its five passages primary instruments first (Acts, Rules, Directions, scheme documents, own policies; then FAQs and circulars; parliamentary answers and judgments last). Same passages, new order; `retrieval/source_priority.py` |
| `ANSWERABILITY_THRESHOLD` | unset | Abstain when the top reranker score is below it; chosen on the dev split only (`make retrieval-ladder CURVE=1`, scope #63) |

## Data files
Paths are relative to the repo root. The defaults point at the frozen synthetic data; change them only for tests.

| Variable | Default | Meaning |
|---|---|---|
| `HR_DB` | `data/frozen/v1/hr.db` | Synthetic HR store, opened read-only (ONB-01, ONB-05) |
| `REFERENCE_RATES_FILE` | `data/reference/reference_rates.yaml` | Repo rate and bank EBLR/RLLR as of `AS_OF_DATE`; prices floating-rate offers (LW-08, S22) |
| `LENDER_SCRIPTS_DIR` | `data/frozen/v2/lender_scripts` | Scripted lender replies for the three negotiation rounds (S05 v2, LW-13/15, ADR 0037). A v1 directory answers only round 1 |
| `CORPUS_MANIFEST` | `data/corpus/manifest.yaml` | Lets the Critic and copilot call a cited document superseded even when it was never indexed (VER-02, KR-04) |
| `HOME_STATE` | `IN-MH` | Home jurisdiction for the retrieval filter; other states' documents are never cited as current (ADR 0019, KR-04) |

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
| `APPROVAL_THRESHOLD_PAISE` | 1,500,000,000 | ₹1.5 crore in paise. **Not read yet:** routing and step-up use `engines.routing.THRESHOLD` (one source for the number) |
| `APPROVAL_STEP_UP` | true | Approving more than ₹1.5 crore needs the approver's password again (403 `STEP_UP_REQUIRED`) |
| `GST_RATE` | 0.18 | GST on fees, never on interest |
| `APR_CONVENTION` | `nominal` | `nominal` or `effective` (ADR 0012) |
| `FORECAST_WEEKS` | 26 | Cash-flow horizon |
| `AGENT_MAX_STEPS` / `TOKEN_CAP_PER_STAGE` | 10 / 6000 | Per-invocation caps (SUP-07) |
| `AS_OF_DATE` | 2026-11-15 | Fixed "today" so results reproduce |
| `CREDASSURE_SEED` | 20261026 | Seed for the data generators |
| `PLANNER_MODE` | `fixed` | `fixed` or `llm_proposes` (code validates) |
| `FEATURE_STRETCH` | `false` | BRD §4.2 stretch items |
| `ABLATION` | unset | A1 to A5; evaluation only |
| `EVAL_DIR` | `var/eval` | Harness run folders the evaluator scorecard reads (P9 U5) |
| `BASELINE_DIR` | `evaluation/baseline/results` | Baseline S1–S3 result files the scorecard reads (P9 U5) |

## End-to-end tests
`E2E_USERNAME`, `E2E_PASSWORD`, `E2E_BASE_URL`, `E2E_API_URL`: read by Playwright. The `make e2e*` targets set the URLs themselves, so don't put `E2E_*` URLs in `.env`.
