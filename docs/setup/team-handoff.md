# Team handoff: continue a module with Claude Code, Cursor or another AI tool

This page is how a teammate picks up a module (enhancement, development or optimisation) **without losing the project's
context, rules and guardrails**, whichever AI assistant they use. Setup first: [local-dev.md](local-dev.md).

## 1. Where the context lives

Everything a teammate needs is **in git**. Chat history and personal AI memory are not shared, so anything that matters
must be written into one of the shared files below.

| Layer | Claude Code | Cursor | Other tools (Codex, Copilot, Windsurf, Gemini…) |
|---|---|---|---|
| Project instructions (loaded automatically) | [CLAUDE.md](../../CLAUDE.md), which imports the BRD, architecture, data spec, ADRs and `.cursor/rules` | `.cursor/rules/*.mdc` (00 and 10 always; 20, 30, 40 when you touch matching paths) + [AGENTS.md](../../AGENTS.md) | [AGENTS.md](../../AGENTS.md); if the tool doesn't load it, attach it to the first message |
| Guardrails | **Enforced** by `.claude/hooks/` (blocks `.env`, certificates, frozen sets, `git push`, `rm -rf`; runs `make check-fast` on stop) and `.claude/settings.json` permissions | **Not enforced** in this repo. Follow the checklist in §4 | **Not enforced.** Follow §4 |
| Workflows | `/status`, `/next`, `/phase <n>`, `/gate <G>`, `/eval <E#>`, `/review`, `/ui U<n>` | Paste a step from `prompts/NN-*.md` (or [CURSOR_MASTER_PROMPT.md](../../CURSOR_MASTER_PROMPT.md)) into Agent chat, Plan mode | Paste the same `prompts/NN-*.md` step |
| Reviewers | Subagents in `.claude/agents/`: `brd-conformance`, `security-reviewer`, `money-auditor`, `test-writer`, `eval-analyst` | Ask the chat to review the diff against `.claude/agents/<name>.md` as a checklist | Same as Cursor |

**Shared state (all tools):**
- [PROGRESS.md](../../PROGRESS.md): generated status (gates, latest step entries, modules, open items), built by `make progress` from `docs/progress/`; the history before 2026-11-18 is in `docs/progress/HISTORY.md`.
- `agents/<module>/README.md` (agent card) and `agents/<module>/agent.yaml`: inputs, tools, ledger writes, gate rule, owner.
- `docs/adr/`: every decision that changes a contract, a default or a rule (index: [docs/adr/README.md](../adr/README.md)).
- `evaluation/reports/`: evidence for each evaluation run.

**Not shared:** Claude Code memory (`~/.claude/...`), Cursor chat history, your `.env`, `var/` (databases, Chroma, caches).

## 2. Handing a module off (outgoing owner)
1. `make check` is green.
2. Record progress (never edit `PROGRESS.md` by hand):
   - add one entry file in `docs/progress/entries/` (copy `TEMPLATE.md`): what was done with requirement IDs, decisions, what's open;
   - update your module file in `docs/progress/modules/` (status, open items, the exact next step);
   - run `make progress`.
3. Update `agents/<module>/README.md` if its inputs, tools, ledger writes, blockers or gate changed.
4. New decision → a new ADR in `docs/adr/` plus a line in `docs/adr/README.md`.
5. API changed → `make openapi && make client`. Evaluation run → report in `evaluation/reports/`.
6. Commit `phase-N: <summary> [REQ-IDs]` on a branch (`phase-N-short-name`, see [CONTRIBUTING.md](../../CONTRIBUTING.md)). A human pushes and opens the PR.

Never pass `.env`, keys or passwords through chat or PRs; each person keeps their own (see [environment.md](environment.md)).

## 3. Picking a module up (incoming owner)
1. `git pull`, then `make install && npm install`, then create your own `.env` ([environment.md](environment.md)).
2. If `var/` is empty: `make hr-db && make db && make ingest`, then `make check`. (`make data` refuses once `data/frozen/v1` is frozen; the frozen files are in git and `make hr-db` rebuilds the gitignored HR store from them.)
3. Read, in this order:
   1. `PROGRESS.md` (generated) and your module file in `docs/progress/modules/`.
   2. `agents/<module>/README.md`.
   3. The module's rows in the [module map](#5-module-map) below: BRD section, design-detail section, ADRs.
4. Start the AI session (next section).

### Start the session

| Tool | How |
|---|---|
| **Claude Code** | Open at the repo root, plan mode on, run `/status`, then paste the kickoff prompt. To continue a numbered phase, use `/phase <n>` or `/next` instead |
| **Cursor** | Agent chat in **Plan** mode. Paste the kickoff prompt and `@`-attach `PROGRESS.md`, `AGENTS.md` and the module card. Check that rules 00 and 10 show as applied |
| **Other tools** | Paste the kickoff prompt; attach `AGENTS.md` if the tool doesn't load it on its own |

**Kickoff prompt** (works in every tool; fill in the brackets):

```text
I'm continuing the <module> module of CredAssure (owner: <name>). Task: <enhancement / bug / optimisation, one sentence>.

Before proposing anything:
1. Read AGENTS.md (or CLAUDE.md), PROGRESS.md, agents/<module>/README.md and the rules in .cursor/rules/.
2. Read the requirement IDs in scope: <e.g. LW-04, LW-09> from docs/requirements/BRD.md and
   docs/architecture/design-detail.md §<2.4.x>, plus any ADR they cite.
3. Summarise in 5 lines: what exists, what's open for this task in PROGRESS.md and the module file, and which rules apply.

Then give a plan only (no code yet): files to change, tests to write first, requirement IDs, and the evaluation or
acceptance line that proves it. Respect the non-negotiables: code calculates and gates, the model only explains;
money in Decimal/paise; no agent-to-agent imports; frozen sets untouched; no offer acceptance path.
After I approve: tests first, implement, run `make check`, add a progress entry and update the module file
(docs/progress/, then make progress) and the module card, and propose a
commit message `phase-N: <summary> [REQ-IDs]`. Don't push.
```

## 4. Guardrail checklist (mandatory in Cursor and other tools)
Claude Code's hooks block most of these automatically. In other tools, check them yourself before every commit:

- [ ] No gate decision set by model output; every number comes from `packages/engines` and goes through the ledger.
- [ ] No floats for money; Decimal in Python, paise in SQLite.
- [ ] No import between agents (`make check` runs import-linter).
- [ ] Nothing changed under `evaluation/testset/v1/`, `evaluation/retrieval/v1/` or `data/frozen/v1/`.
- [ ] `.env`, certificates and raw corpus files not read into chat, not staged (`git status`).
- [ ] No accept/sign/submit path for lender offers; negotiation stays a draft for a human.
- [ ] Prompt changed → version bumped and `make eval-fast` passes.
- [ ] API changed → `make openapi && make client`.
- [ ] Requirement IDs in docstrings and test names; `make check` green.
- [ ] Progress entry added, module file and module card updated, `make progress` run (`PROGRESS.md` never edited by hand).

## 5. Module map

| Module | Owner | Code | Requirements | Design | Acceptance | Reviewers |
|---|---|---|---|---|---|---|
| Supervisor, routing, gateway | [Name 1] | `agents/supervisor`, `apps/gateway`, `deploy/` | SUP-01..08, APR-01..06, API-01 | design-detail §2.2, §2.4.1, §3; ADR 0007, 0008 | isolation 3/3, routing 6/6, end-to-end ≥4/5 | security-reviewer, brd-conformance |
| Employee Onboarding | Tejas | `agents/onboarding` | ONB-01..07 | §2.4.2 | onboarding 10/10 | security-reviewer, brd-conformance |
| Working Capital | Suresh | `agents/working-capital`, `packages/engines` (cash flow) | WC-01..08, BR-01, BR-02 | §2.4.3; ADR 0010, 0011 | cash flow 15/15 to ₹1, bridge sums exactly | money-auditor, brd-conformance |
| LendWise | Pritish | `agents/lendwise`, `packages/engines` (loan cost), `packages/lender-sim` | LW-01..15, BR-06..10 | §2.4.4, §2.4.7; ADR 0012, 0023 | offers 15/15, negotiation 5/5 | money-auditor, security-reviewer |
| Verification Critic | Abhishek | `agents/critic`, `packages/observability` | VER-01..06 | §2.4.5 | bad-citation plants 12/12, safety items | security-reviewer, brd-conformance |
| Ask CredAssure Copilot | [Name 6] | `agents/copilot`, `packages/retrieval`, `data/corpus` | KR-01..05, CP-01..04 | §2.4.6; ADR 0013, 0019 | regulatory ≥20/25, refusal 8/8, injection 8/8, isolation 3/3, retrieval ≥34/40 | security-reviewer |
| Web UI | UI lead | `apps/web`, `packages/api-client` | UI-01..10 | [docs/ui/DESIGN_BRIEF.md](../ui/DESIGN_BRIEF.md), `CLAUDE_CODE_UI_PROMPT.md`; ADR 0004 | Playwright e2e (`make e2e`), no business logic in the UI | security-reviewer |
| Evaluation | Abhishek, Tejas | `evaluation/` | BRD §12–13 | [docs/build/PHASE_PROMPTS.md](../build/PHASE_PROMPTS.md) Phases 3, 11 | ≥92/100 and above the best baseline | eval-analyst |

Rule of thumb: **one module, one branch, one session per task.** If a change touches a shared package
(`packages/core`, `packages/engines`, `packages/ledger`), say so in the PR. Shared packages need two reviewers (CODEOWNERS).
