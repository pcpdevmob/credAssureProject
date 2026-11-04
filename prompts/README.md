# CredAssure — Step-by-step prompts (run in order)

Each file has: when, owner, prerequisites, what humans must do, the paste block, the scope items it closes, evaluations to run, and done criteria.
Paste the block into Claude Code (plan mode) at the repo root. Start each step in a fresh session (`/clear`).
The same steps run automatically with `/build-all`; use these files when you want to drive each step yourself or hand a step to its owner.

| # | Step | Week | Owner | Scope items | Evals |
|---|---|---|---|---|---|
| 00 | [Kick-off: load context, find conflicts](00-kickoff.md) | W1 D1 | Integration lead | — | — |
| 01 | [Phase 0 — tooling, CI, config](01-phase0-setup.md) | W1 D1 | Integration lead | 30, 31, 42, 43, 44 | — |
| 02 | [Phase 0b — monorepo scaffold (ADR 0005)](02-scaffold-monorepo.md) | W1 D1–2 | Integration lead | 27, 28, 29, 46 (ports skeleton), 53 (import-linter) | — |
| 03 | [Phase 1 — shared contract, money, normaliser](03-phase1-contracts.md) | W1 D2 | Supervisor owner + all | 8, 9, 21 (schema), 24, 25 (agent_version), 26, 32, 46 | E4 (normaliser part) |
| 04 | [Phase 2 — synthetic data and open corpus](04-phase2-data.md) | W1 D2–4 | Copilot owner (corpus) + WC/LendWise owners (generators) | 14 | E1, E2 |
| 05 | [Phase 3 — test set, gold, baseline](05-phase3-eval-assets.md) | W1 D3–5 | Onboarding owner (lead) + all | 13 | — |
| 06 | [Gate G1 and freeze](06-gate-g1-freeze.md) | W1 D5 | Integration lead | — | — |
| 07 | [Phase 8 — walking skeleton](07-phase8-skeleton.md) | W1 D4–W2 D1 | Supervisor owner | 4, 15, 16, 19, 47, 50 | E9, E11 |
| 08 | [Phase 5 — database, ledger, audit, auth](08-phase5-storage.md) | W2 D1 | Supervisor owner | 22 (DB part), 49 | E10 (auth part) |
| 09 | [Phase 4 — calculation engines](09-phase4-engines.md) | W2 D1–3 | WC owner + LendWise owner (Pritish) | 7 | E3 |
| 10 | [Phase 6 — model layer and guardrails](10-phase6-llm.md) | W2 D2–3 | Critic owner + Supervisor owner | 22 (limiter), 23, 36, 48 | E4 |
| 11 | [Phase 7 — retrieval](11-phase7-retrieval.md) | W2 D3–4 | Copilot owner | — | E8 (retrieval part) |
| 12 | [UI U0–U1 — design plan and foundations](12-ui-u0-u1.md) | W2 | UI lead | 52 | — |
| 13 | [Phase 9a — Employee Onboarding agent](13-phase9a-onboarding.md) | W2 D3–5 | Onboarding owner | — | E5 |
| 14 | [Phase 9b — Working Capital agent](14-phase9b-working-capital.md) | W2 D3–5 | WC owner | — | E6 |
| 15 | [Gate G2](15-gate-g2.md) | W2 D5 | Integration lead | — | — |
| 16 | [Phase 9c — LendWise agent](16-phase9c-lendwise.md) | W3 D1–3 | LendWise owner (Pritish) | 22 (parallel calls) | E7 |
| 17 | [Phase 9d — Verification Critic](17-phase9d-critic.md) | W3 D1–3 | Critic owner | 1, 10, 21 | E4 |
| 18 | [Phase 9e — Ask CredAssure copilot](18-phase9e-copilot.md) | W3 D1–3 | Copilot owner | 2, 20, 40 | E8 |
| 19 | [UI U2–U4 — preparer flow, analysis, copilot and approvals](19-ui-u2-u4.md) | W3 | UI lead | — | — |
| 20 | [Phase 10 — reports, approvals, explainability](20-phase10-reports-approvals.md) | W3 D3–5 | Supervisor owner + WC owner | 6, 33, 39, 51 | E10, E17 (items due) |
| 21 | [Gate G3 and architecture check](21-gate-g3.md) | W3 D5 | Integration lead | 53 | E18 |
| 22 | [Phase 11 — evaluation, ablations, red-team](22-phase11-evaluation.md) | W4 D1–3 | Critic owner + Onboarding owner | 5, 11, 12, 34, 35 | E12, E13, E14, E16 |
| 23 | [UI U5–U6 — evaluator, help, hardening](23-ui-u5-u6.md) | W4 | UI lead | — | — |
| 24 | [Phase 12 — ship](24-phase12-ship.md) | W4 D3–4 | Supervisor owner | 3, 17, 18, 37, 38, 41, 45 | E15, E17 |
| 25 | [Gate G4 — final evaluation](25-gate-g4.md) | W4 D5 | Integration lead | all remaining | E12–E18 |
| 26 | [Report, slides and demo script](26-report-and-demo.md) | W4 D4–5 | All (each writes own agent section) | — | — |

## Recovery prompts

- **Drifted from spec:** `Stop. Re-read CLAUDE.md and this step's prompt file. List every place the diff departs from them, then fix only those.`
- **Numbers look wrong:** `Use money-auditor on the last commit; recompute case <id> independently and show the week-by-week difference.`
- **Small model breaks JSON:** `Show the last 5 StructuredOutputError traces; propose prompt or schema changes; do not loosen validation.`
- **Scope creep:** `Compare the diff to BRD §4 and docs/BUILD_SCOPE.md; revert anything out of scope or put it behind FEATURE_STRETCH=false.`
- **Blocked:** `Write the blocker, what you tried and two options into PROGRESS.md, then stop.`
- **Context too long:** `/compact` keeping the current plan, failing tests and open questions; or `/clear` then re-paste the step file.
