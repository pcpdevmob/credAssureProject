# CredAssure — Repository structure

Polyglot monorepo (uv workspace + pnpm workspace). Rationale and import rules: docs/adr/0005-monorepo-structure.md.

```
credassure/
├── README.md                     # what it is, 5-minute quick start, links into docs/
├── CONTRIBUTING.md               # branches, PR template, commit style, ownership
├── SECURITY.md                   # how to report issues; threat-model link
├── CHANGELOG.md                  # Keep a Changelog + semver tags
├── LICENSE                       # MIT (code); data licences in docs/data/
├── CLAUDE.md  START_HERE.md  PROGRESS.md   # PROGRESS.md is generated from docs/progress/ (make progress)
├── pyproject.toml                # uv workspace root (members: agents/*, packages/*, apps/gateway, evaluation)
├── uv.lock
├── package.json  pnpm-workspace.yaml  pnpm-lock.yaml   # JS workspace (apps/web, packages/api-client)
├── Makefile                      # one entry point for every task (see docs/setup/commands.md)
├── .env.example                  # profile templates live in deploy/env/*.env.example (root .env* is hook-guarded)
├── .editorconfig  .gitignore  .gitattributes  .pre-commit-config.yaml  .importlinter
│
├── apps/
│   ├── gateway/                  # FastAPI composition root — the only public API
│   │   ├── pyproject.toml
│   │   ├── src/credassure/gateway/
│   │   │   ├── main.py           # app factory, middleware, mounts /v1 routers
│   │   │   ├── settings.py       # pydantic-settings, validated at startup
│   │   │   ├── deps.py           # auth, roles, tenant + case scoping
│   │   │   ├── routers/          # auth, cases, files, approvals, reports, audit, admin, eval, health
│   │   │   ├── supervisor_service.py   # interface agent routers use to run a stage
│   │   │   └── openapi.py        # export openapi.json
│   │   └── tests/                # contract tests per route, auth/role tests
│   └── web/                      # React UI (see CLAUDE_CODE_UI_PROMPT.md)
│       ├── package.json  vite.config.ts  tsconfig.json  index.html
│       ├── src/
│       │   ├── app/              # providers, router, layout shell, error boundary
│       │   ├── features/         # one folder per domain: cases, upload, workflow, funding, offers,
│       │   │                     #   copilot, approvals, reports, audit, evaluation, help, auth
│       │   ├── components/       # shared UI built on accessible primitives
│       │   ├── design/           # tokens.css, typography, motion, theme (light/dark)
│       │   ├── lib/              # money (Indian grouping), dates, api hooks, errors
│       │   ├── content/help/     # built from docs/help at build time
│       │   └── mocks/            # MSW handlers generated from OpenAPI examples
│       ├── tests/  e2e/          # Vitest + RTL; Playwright + axe
│       └── README.md
│
├── agents/                       # one self-contained project per agent
│   ├── supervisor/
│   ├── onboarding/
│   ├── working-capital/
│   ├── lendwise/
│   ├── critic/
│   └── copilot/
│       ├── pyproject.toml        # name: credassure-agent-copilot
│       ├── README.md             # agent card: purpose, owner, requirement IDs, tools, data access, gate rule, eval category
│       ├── agent.yaml            # registry entry (inputs, outputs, tools, readable data, owner, version)
│       ├── src/credassure/agents/copilot/
│       │   ├── agent.py          # bounded loop (≤10 steps), returns AgentResult
│       │   ├── tools.py          # allowlisted tools only
│       │   ├── prompts/          # versioned YAML prompts
│       │   ├── memory.py         # (copilot only) per-case conversation state
│       │   └── api/              # this agent's API layer
│       │       ├── router.py     # APIRouter mounted at /v1/agents/copilot
│       │       ├── schemas.py    # request/response models for this agent's endpoints
│       │       └── deps.py       # agent-specific dependencies (uses gateway auth)
│       └── tests/
│           ├── unit/             # FakeLLM, no network
│           ├── api/              # router tests through TestClient
│           └── fixtures/
│
├── packages/                     # shared libraries (no agent imports)
│   ├── core/                     # AgentResult, enums, money, errors, blockers, findings, Plan
│   ├── engines/                  # pure calculations (cash flow, loan cost, affordability, ranking, routing, normaliser)
│   ├── ledger/                   # SQLAlchemy models, Alembic migrations, fact ledger, hash-chained audit
│   ├── llm/                      # client, structured output, prompt registry, cache, budget, limiter, timeouts
│   ├── retrieval/                # ingestion, chunkers, FTS5, Chroma, fusion, reranker, filters
│   ├── security/                 # auth, PII redaction, spotlighting, injection scanner
│   ├── tools/                    # tool registry + data-access matrix enforcement
│   ├── lender-sim/               # deterministic lender simulator
│   ├── reports/                  # Jinja2 templates, sections.yaml, versioning
│   ├── observability/            # Langfuse wiring, structured logging, metrics
│   └── api-client/               # TypeScript client generated from openapi.json (pnpm package)
│
├── data/
│   ├── generators/               # seeded synthetic data (S01–S24)
│   ├── reference/                # S22 parameter tables (AGF slabs, GST, reference rates)
│   ├── frozen/v1/                # frozen at G1 (hash manifest, FROZEN marker)
│   └── corpus/                   # manifest.yaml, download.py, audit.py (raw/text gitignored)
│
├── evaluation/                   # its own uv project
│   ├── testset/v1/  retrieval/v1/  redteam/
│   ├── gold/                     # independent calculators (no engine imports)
│   ├── baseline/                 # S1–S3
│   ├── ablations/                # A1–A5 configs + modes
│   ├── judge/                    # J1 prompt, calibration labels, agreement
│   ├── harness/                  # runs items through the gateway API
│   └── reports/                  # generated scorecards (committed per release)
│
├── deploy/
│   ├── docker/                   # Dockerfile.gateway, Dockerfile.web (multi-stage, non-root)
│   ├── compose/                  # compose.yaml + profiles: dev, test, demo; langfuse; chroma
│   ├── scripts/                  # backup.sh, restore.sh, demo-reset.sh, healthcheck.sh
│   └── env/                      # documented env templates per profile
│
├── docs/                         # Diátaxis-style documentation
│   ├── README.md                 # docs index
│   ├── requirements/BRD.md
│   ├── architecture/             # ARCHITECTURE.md (arc42 + C4), design-detail.md (agents, schema, APIs)
│   ├── adr/                      # decisions
│   ├── data/                     # DATA_RESOURCES.md, DATA_SPEC.md, RESOURCES.md, licences
│   ├── setup/                    # prerequisites, local-dev, environment variables, data and corpus, commands, troubleshooting
│   ├── deployment/               # compose, environments, release, backup-restore, observability, RUNBOOK.md
│   ├── evaluation/               # methodology, metrics, how to run, latest results
│   ├── help/                     # end-user help: getting started, preparer, approver, evaluator, FAQ, glossary, error messages
│   ├── security/                 # threat model, risk register (OWASP LLM Top 10 mapping), model card
│   ├── ui/                       # DESIGN_BRIEF.md, design plan, screen inventory
│   └── build/                    # PHASE_PROMPTS.md, BUILD_SCOPE.md, REPO_STRUCTURE.md (this file)
│
├── .github/
│   ├── workflows/ci.yml          # restored (ADR 0028); .githooks/pre-push runs the same gates locally (ADR 0027)
│   ├── CODEOWNERS                # one owner per agents/<x>/, shared packages need two reviewers
│   └── pull_request_template.md  # requirement IDs, scope items, eval impact, screenshots for UI
├── .claude/                      # Claude Code settings, hooks, commands, subagents
└── .cursor/                      # Cursor rules
```

## Ownership
| Path | Owner |
|---|---|
| agents/supervisor, apps/gateway | Abhishek |
| deploy/ | Suresh |
| agents/onboarding | Mousita (0.3.0; Tejas built 0.1–0.2) |
| evaluation/testset | Tejas |
| agents/working-capital, packages/engines (cash flow) | Suresh |
| agents/lendwise, packages/engines (loan cost), packages/lender-sim | Pritish |
| agents/critic, packages/observability, evaluation/ablations | Abhishek |
| agents/copilot | Adesh |
| packages/retrieval | Adesh, Tejas |
| data/corpus | Tejas, Pritish |
| apps/web, packages/api-client | Suresh |

## Agent API endpoints (mounted under /v1/agents/<name>)
| Endpoint | All agents | Notes |
|---|---|---|
| GET /card | ✓ | agent.yaml + version + prompt versions |
| GET /health | ✓ | dependencies this agent needs |
| POST /cases/{case_id}/run | onboarding, working-capital, lendwise, critic | Calls supervisor_service.run_stage(); gates enforced |
| GET /cases/{case_id}/result | ✓ | latest AgentResult for the case |
| Agent-specific | | working-capital: GET /cases/{id}/cash-table · lendwise: GET /cases/{id}/offers, POST /cases/{id}/negotiate · critic: GET /cases/{id}/findings · copilot: POST /cases/{id}/chat · supervisor: GET /cases/{id}/plan, POST /cases/{id}/stages/{stage}/retry |
