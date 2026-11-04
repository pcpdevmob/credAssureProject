# ADR 0005 — Monorepo structure: one project per agent, shared packages, React UI

Status: Accepted · Date: 2026-11-04 · Supersedes the layout in ARCHITECTURE.md §1 and the Streamlit client in ADR 0004 (API-first stays)

## Decision
A polyglot monorepo: a **uv workspace** for Python (one member per agent, per shared package, the gateway and evaluation) and a
**pnpm workspace** for TypeScript (the React web app and the generated API client).

- Each agent is its own project (`agents/<name>/`) with its own `pyproject.toml`, tests, prompts, README (agent card) and an `api/` folder.
- An agent's `api/` folder holds a FastAPI `APIRouter` that the **gateway** mounts under `/v1/agents/<name>`. It exposes the agent's
  card, health, stage run and read endpoints. A stage run goes **through the Supervisor**, never straight into the agent,
  so gates, caps and audit always apply (BRD §6, ADR 0003 §8).
- Default deployment is one gateway process mounting every router (modular monolith). Because each agent ships its own router,
  any agent can later run as its own service without code changes — the enterprise path.
- Python uses a PEP 420 namespace package `credassure.*` across members, so imports stay `credassure.engines`, `credassure.agents.lendwise`.
- The web app talks only to the gateway through a TypeScript client generated from `openapi.json`.

## Why not fully separate repos or services per agent
Separate repos break the frozen shared contract (AgentResult, money, ledger) into versioned dependencies that six people must
keep in sync in four weeks; separate services add network hops, auth between services and failure modes the BRD does not need.
The monorepo keeps one contract, one CI, atomic changes across agents, and still gives each owner a self-contained project.

## Boundaries (enforced by import-linter in CI)
1. `agents/*` may import `packages/*`; never another agent.
2. `packages/*` never import `agents/*` or `apps/*`.
3. Agent `api/` routers call the Supervisor service interface, not another agent's internals.
4. `apps/web` calls only `packages/api-client`; no hand-written fetch to the backend.
5. Only `packages/ledger` writes ledger facts and audit events.
6. Only `packages/llm` imports the OpenAI SDK.

## Path map (older docs → this layout)
| Older path | New path |
|---|---|
| `src/credassure/domain/` | `packages/core/src/credassure/core/` |
| `src/credassure/engines/` | `packages/engines/src/credassure/engines/` |
| `src/credassure/ledger/`, `db/` | `packages/ledger/src/credassure/ledger/` (models, migrations, ledger, audit) |
| `src/credassure/llm/` | `packages/llm/src/credassure/llm/` |
| `src/credassure/retrieval/` | `packages/retrieval/src/credassure/retrieval/` |
| `src/credassure/security/` | `packages/security/src/credassure/security/` |
| `src/credassure/observability/` | `packages/observability/src/credassure/observability/` |
| `src/credassure/tools/` | `packages/tools/src/credassure/tools/` |
| `src/credassure/lender_sim/` | `packages/lender-sim/src/credassure/lender_sim/` |
| `src/credassure/reports/` | `packages/reports/src/credassure/reports/` |
| `src/credassure/agents/<x>/` | `agents/<x>/src/credassure/agents/<x>/` |
| `src/credassure/api/` | `apps/gateway/src/credassure/gateway/` |
| `ui/` (Streamlit) | `apps/web/` (React) |
| `eval/` | `evaluation/` |
| `docs/*.md` (flat) | `docs/<section>/` per the tree in docs/REPO_STRUCTURE.md |
