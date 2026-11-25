# CredAssure — Start here

## 1. What this kit is
Everything the coding tool (or Cursor) needs to build CredAssure end to end as an enterprise-grade application at capstone scale,
using only open data. Unzip into an empty repo root.

## 2. The fastest path
Run the prompts in `prompts/` in order (index: `prompts/README.md`, 27 steps from kick-off to final report), or run `/build-all` to have the coding tool drive the same sequence.

## 2b. Reading order
| # | File | What it gives you |
|---|---|---|
| 1 | `docs/BRD.md` | Requirements v3.1 (source of truth) |
| 2 | `docs/architecture/ARCHITECTURE.md` | arc42 + C4 architecture; detail appendix `docs/architecture/design-detail.md` |
| 3 | `docs/DATA_RESOURCES.md` | All 32 public + 17 synthetic data resources, legal basis per item |
| 4 | `docs/DATA_SPEC.md` | Synthetic data schemas and planted cases |
| 5 | `docs/RESOURCES.md` | Design impacts D1–D8 from regulatory sources |
| 6 | `docs/BUILD_SCOPE.md` | Complete build scope (53 items) tagged by phase, plus settled decisions |
| 7 | `docs/PHASE_PROMPTS.md` | Phases 0–12 |
| 8 | `docs/adr/` | Decisions 0003 (execution guide), 0004 (UI deferred, API-first) |
| 9 | `the build prompt` | The end-to-end prompt |
| 9a | `docs/REPO_STRUCTURE.md` + `docs/adr/0005-monorepo-structure.md` | Monorepo layout, ownership, agent API endpoints |
| 9b | `the build prompt` | Prompt A: scaffold the monorepo (`/scaffold-repo`) |
| 9c | `the build prompt` + `docs/ui/DESIGN_BRIEF.md` | Prompt B: React web app with frontend-design (`/ui U0..U6`) |
| 10 | the tool configuration | Evaluation prompts E1–E17 + judge prompt J1 |

Original project files: `docs/source/`. Companion documents: `docs/reference/README.md`.

Companion documents (shareable, same content in long form):
- Enterprise production architecture and delivery plan — (external reference removed)
- Capstone architecture and open data plan — (external reference removed)
- Capstone build pack (data list, architecture, steps, build scope, eval prompts) — (external reference removed)

## 3. Human prerequisites (before running anything)
- [ ] Course chat endpoint URL, model name, API key, embeddings endpoint — put in `.env` after Phase 0 creates `.env.example`
- [ ] Langfuse: self-hosted in Compose (ADR 0016, no account needed): copy `deploy/env/langfuse.env.example` to `deploy/env/langfuse.env`, replace every CHANGEME, `make langfuse-up`, then put the project keys in `.env`
- [ ] Python 3.12, uv, Docker Engine + Compose, the coding tool installed
- [ ] Team owners named in `docs/BUILD_SCOPE.md` / `CONTRIBUTIONS.md` ([Name 1]…[Name 6])
- [ ] Mentor informed of the defaults in ADRs 0013–0015 (reranker, judge, demo); none blocks the build

## 4. Run
1. `git init && git add -A && git commit -m "kit"`
2. Start the coding tool at the repo root → `/agents` (5 subagents) → `/status`
3. Paste the block from `the build prompt` in plan mode, or run `/build-all`
4. Per phase you can also run `/phase <n>`, `/gate <G>`, `/eval <E#>`, `/review`, `/next`

## 5. Commands
`/build-all` · `/scaffold-repo` · `/ui U0..U6` · `/phase <n>` · `/next` · `/gate G1|skeleton|G2|G3|G4` · `/freeze-g1` · `/eval E1..E17|all-modules|app` · `/review` · `/status`
