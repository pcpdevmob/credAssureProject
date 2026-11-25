# ADR 0001 — Technology stack

Status: Accepted · 2026-11-05

## Decision
| Concern | Choice | Notes |
|---|---|---|
| Language / packaging | Python 3.12, uv workspace (ADR 0005) | `uv.lock` pins everything; never `pip install` globally |
| API | FastAPI + Pydantic v2, served by uvicorn | `/v1` prefix, RFC 9457 errors, `openapi.json` exported (ADR 0004) |
| Settings | pydantic-settings, validated at startup | Fail closed when required secrets are missing outside test mode |
| Orchestration | LangGraph + `langgraph-checkpoint-sqlite` | Code-decided edges; the model never sets a gate |
| Storage | SQLAlchemy 2 + Alembic on SQLite (WAL) | `case.db`, read-only `hr.db`, `corpus.db` |
| Retrieval | SQLite FTS5 (BM25) + Chroma (dense) + RRF | Reranker per ADR 0013 (optional extra `rerank`). Chroma is added in Phase 7 under `packages/retrieval`, embedded (`PersistentClient`) only, never server mode: pip-audit on 5 Nov 2026 reported 5 unfixed chromadb 1.5.9 advisories, all in the HTTP server (PYSEC-2026-311, -3813, -3814, -3815). Phase 7 records the exception or an alternative in an ADR. |
| Model access | `openai` SDK against an OpenAI-compatible ≤8B endpoint | Local default is Ollama `qwen3:8b` plus `nomic-embed-text` (ADR 0017). Graded eval points the same settings at the course endpoint. Imported only by `packages/llm` (ADR 0005 boundary 6). |
| Tracing | Langfuse, self-hosted (ADR 0016) | PII mask on every span |
| Auth | PyJWT (HS256, 30 min) + argon2-cffi | Roles per the tool configuration |
| Limits / retries | slowapi, tenacity | Token-budget guard on every model call |
| Templates | Jinja2 (autoescape on) | Reports and fallback templates |
| Web UI | React app in `apps/web` (ADR 0005); Streamlit reference client only until it lands | No business logic in the UI |
| Quality | ruff, mypy --strict, pytest + hypothesis, bandit, pip-audit, gitleaks, pre-commit | `make check` is the gate |
| Deployment | Docker Compose with `dev`, `test`, `demo`, `langfuse` profiles | Images pinned by digest in Phase 12 |

## Rules
- Substituting any row needs a new ADR (the tool configuration).
- Money is `Decimal` in Python and integer paise in SQLite; no floats outside `evaluation/gold/`.
