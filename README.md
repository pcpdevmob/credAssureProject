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

Order: Phase 0 → 3 must finish before any agent code (G1). Each team member then runs their Phase 9
prompt on their own branch; merge through PRs with `make check` green.
