# Commands

`make help` lists every target. Add `MODELS=course` to any target that calls the model to use the graded endpoints
(default `MODELS=local`, Ollama). Run `make` from the repo root.

## Setup and quality
| Command | What it does |
|---|---|
| `make install` | `uv sync --all-packages --all-extras`: all workspace members, the dev group and extras (`rerank`: sentence-transformers for embeddings and the reranker) |
| `make check` | ruff, ruff format, mypy --strict, pytest, corpus refs, bandit, import-linter. **Green before every commit** |
| `make check-fast` | ruff + tests not marked slow (the coding tool stop hook runs it) |
| `make test` | Full suite with coverage |
| `make audit` | pip-audit (accepted advisories: `docs/security/risk-register.md`) |

## Run
| Command | What it does |
|---|---|
| `make start` | Everything at once: course endpoint by default (`MODELS=local\|hf`), Langfuse if set up, API, web; database and users on first run, no cases. `ARGS="--no-model --no-langfuse --no-ui --install"` |
| `make stop` | Stop what `make start` started (Langfuse: `make langfuse-down`) |
| `make run-api` | Gateway on :8000, tenant `demo`, `var/case.db` |
| `make run-ui` | Next.js web app on :3000 |
| `make db` | Migrate `var/case.db` + `var/corpus.db`, create missing accounts, each with its own first password (`var/initial-passwords.txt`) |
| `make passwords` | New own password for every seeded account (`var/initial-passwords.txt`); signs them out, keeps MFA |
| `make onboarding-prototype` | Tests of Mousita's stand-alone onboarding prototype (`agents/onboarding/prototype`, not wired into the app); part of `make check` |
| `make demo-reset` | Rebuild the 10 demo cases through the API. **Stop `make run-api` first** |
| `make e2e-db` / `run-api-e2e` / `run-ui-e2e` / `e2e` | Isolated Playwright stack (:8001, :3001, `var/case-e2e.db`) |

## Docker and tracing
| Command | What it does |
|---|---|
| `make up` | Gateway, web (:5173), Ollama and Langfuse (dev profile) |
| `make down` | Stop the dev stack |
| `make compose-dev` / `compose-test` / `compose-demo` | One profile: dev, test (LLM off, no tracing), demo |
| `make langfuse-up` / `langfuse-down` | Self-hosted Langfuse only (needs `deploy/env/langfuse.env`) |
| `make ollama-pull` | Download `qwen3:8b` and `nomic-embed-text` |
| `make backup` / `make restore` | Database backup and restore |

## API contract
| Command | What it does |
|---|---|
| `make openapi` | Export `openapi.json` |
| `make client` | `openapi` + regenerate `packages/api-client`. Run after any API change |

## Data and corpus
| Command | What it does |
|---|---|
| `make data` | Seeded synthetic data into `data/frozen/v1` (idempotent; refuses once frozen) |
| `make hr-db` | Rebuild the gitignored `hr.db` from frozen `hr/profiles.json` (fresh clone, CI) |
| `make progress` | Regenerate `PROGRESS.md` from `docs/progress/` (never edit it by hand) |
| `make progress-check` | Fail if `PROGRESS.md` is stale or a progress entry is invalid (in `make check`, `check-fast`, CI) |
| `make ingest` | Index the corpus + synthetic documents (FTS5 + Chroma). Re-run after changing `MODELS` or the corpus |
| `make corpus-status` / `corpus-report` | Real, available and manual-pending counts against the 500 target |
| `make corpus-harvest` / `corpus-download` | Network, 1 request/s, stops on a block |
| `make corpus-import` / `corpus-verify` | Import hand-saved files; check SHA-256 against `manifest.lock.json` |
| `make corpus-audit` / `corpus-dates` / `corpus-junk` / `corpus-export` | Legal-basis audit, effective dates, junk pages, index export |

## Evaluation
| Command | What it does |
|---|---|
| `make retrieval-eval` | recall@5/@10 across 3 retrievers × 3 chunkers × rerank |
| `make retrieval-pool` / `retrieval-silver` | Blind pooled top-5; silver labels |
| `make judge JUDGE=<name>` / `make kappa JUDGE=<name>` | Human judging sample; Cohen's κ vs silver |
| `make baseline` | Prompt baselines S1–S3 |
| `make copilot-live` | 44 copilot items through the API on the configured model |
| `make eval-fast` | Prompt version check + offline prompt subset |
| `make llm-probe` | Endpoint check: guided JSON, thinking switch |
| `make eval` | Full 100-item harness (Phase 11; not implemented yet) |

## Rules
Full checklist for every AI tool: [team-handoff.md §4](team-handoff.md#4-guardrail-checklist-mandatory-in-cursor-and-other-tools).
- Never run a bare `uv sync`; use `make install`.
- Never edit `evaluation/testset/v1/`, `evaluation/retrieval/v1/` or `data/frozen/v1/` once frozen.
- Never print or commit `.env`.
- The coding tool never pushes; review the diff and push yourself.
