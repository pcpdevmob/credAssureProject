# CredAssure — Build Kit (Claude Code and Cursor)

Drop these files into the root of an empty repo.
- **Claude Code:** start with `CLAUDE_CODE_PLAYBOOK.md`. `CLAUDE.md`, `.claude/` and `PROGRESS.md` are picked up automatically.
- **Cursor:** start with `CURSOR_MASTER_PROMPT.md`.

Both tools share the same docs and rules. **Read START_HERE.md first.** For a one-shot end-to-end run use `CLAUDE_CODE_MASTER_PROMPT.md` or `/build-all`.

| File | Purpose |
|---|---|
| `CURSOR_MASTER_PROMPT.md` | Paste into Cursor Agent first (Plan mode). Sets non-negotiables, env, way of working. |
| `.cursor/rules/*.mdc` | Auto-loaded rules: context, security guardrails, money rules, agent contract, testing. |
| `docs/BRD.md` | CredAssure BRD v3.1 (source of truth). Images referenced in it are not included. |
| `docs/architecture/ARCHITECTURE.md` | arc42 + C4 architecture, quality scenarios, ADR index; `design-detail.md` holds agent/schema detail. |
| `docs/DATA_SPEC.md` | Synthetic data with planted cases, public corpus sources, eval formats. |
| `docs/RESOURCES.md` | Data sources for every agent with verified URLs, design impacts D1–D8, corpus build plan. |
| `prompts/` | 27 ordered, paste-ready Claude Code prompts (00 kick-off → 26 report and demo) with owners, prerequisites, scope items and evals. |
| `docs/source/`, `docs/reference/` | Original project documents; links to the three long-form companion docs. |
| `docs/REPO_STRUCTURE.md`, `docs/adr/0005-monorepo-structure.md` | Monorepo: one project per agent with its own api/ folder, shared packages, React app, docs, evaluation, deploy. |
| `CLAUDE_CODE_REPO_PROMPT.md`, `CLAUDE_CODE_UI_PROMPT.md`, `docs/ui/DESIGN_BRIEF.md` | Prompts to scaffold the repo and build the React UI. |
| `docs/DATA_RESOURCES.md` | All public + synthetic data resources with legal basis. |
| `.claude/commands/eval.md` | Evaluation prompts E1–E17 and judge prompt J1. |
| `docs/BUILD_SCOPE.md` | Complete build scope: 53 items tagged by phase, plus settled decisions. |
| `docs/PHASE_PROMPTS.md` | Phase 0–12 prompts; 9a–9e are per-agent so each owner runs their own. |
| `data/corpus/manifest.example.yaml` | Template for the public regulatory corpus manifest. |

## Quick start (after Phase 0)
```
make install                 # uv sync (Python 3.12 workspace)
cp .env.example .env         # fill JWT_SECRET (>=32 chars); model defaults are already Ollama
OLLAMA_CONTEXT_LENGTH=8192 ollama serve   # host install; skip if you use Compose
make ollama-pull             # qwen3:8b + nomic-embed-text (about 5 GB, once)
make check                   # ruff, format, mypy --strict, pytest, bandit
make run-api                 # http://localhost:8000/docs
make run-ui                  # web app on http://localhost:3000 (the gateway CORS allows :3000)
make langfuse-up             # self-hosted tracing (ADR 0016); needs deploy/env/langfuse.env
```
Local chat model is Qwen3 8B (`qwen3:8b`, same family as the course `Qwen/Qwen3-8B`) and embeddings are `nomic-embed-text`, both on Ollama (ADR 0017). Graded eval points `LLM_BASE_URL`, `LLM_MODEL`, `EMBED_BASE_URL` and `EMBED_MODEL` at the course endpoint instead; that needs a re-index if the embeddings model changes. Switch all model settings at once with `MODELS=local` (default) or `MODELS=course`, e.g. `make ingest MODELS=course`. `EMBED_BASE_URL=local` runs the course embeddings model (`BAAI/bge-small-en-v1.5`) in-process instead of Ollama's `nomic-embed-text`.

Compose profiles: `make compose-dev` and `make compose-demo` start Ollama and point the gateway at `http://ollama:11434/v1` (`make ollama-pull` then downloads into that container). `make compose-test` keeps the LLM off (FakeLLM arrives in Phase 6). Replay arrives in Phase 12.

## Feature flags and switches (scope #30)
All are validated at startup by `apps/gateway/src/credassure/gateway/settings.py`; defaults are fail-safe.

| Variable | Default | Values | Effect |
|---|---|---|---|
| `APP_ENV` | `dev` | dev, test, demo | `test` relaxes the required-secret checks only |
| `LLM_ENABLED` | `true` | bool | `false` = template fallbacks; `LLM_BASE_URL` then not required |
| `TRACING_ENABLED` | `true` | bool | Langfuse tracing on/off (PII mask always applies) |
| `RERANKER` | `none` | none, local_cross_encoder, llm_pointwise | ADR 0013 |
| `APR_CONVENTION` | `nominal` | nominal, effective | ADR 0012 |
| `BOUNDARY_RULE` | `hold` | hold, director, vp | Exactly ₹1.5 cr routing (APR-03) |
| `PLANNER_MODE` | `fixed` | fixed, llm_proposes | Scope #19; code validates any proposal |
| `FEATURE_STRETCH` | `false` | bool | BRD §4.2 stretch items |
| `ABLATION` | empty | A1..A5 | Evaluation only (BRD §12) |

Order: Phase 0 → 3 must finish before any agent code (G1). Each team member then runs their Phase 9
prompt on their own branch; merge through PRs with `make check` green.
