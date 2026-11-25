# Contribution map: commits and PRs by module

Generated from `main` at `0257982` (2026-11-25) by `scripts/contribution_map.py`.

**Ownership, not authorship.** *Owner* is who is responsible for the module (`.github/CODEOWNERS`, set 25 Nov 2026). *Git identities* is who made the commits. Most of the repository was committed from Pritish's machine (identities `pcpdev`, `Pritish`, and `Claude` for commits made with Claude Code there), so a module's owner may not appear among its committers. Where a member wrote code that was committed from that machine, they list it in their own signed statement in `CONTRIBUTIONS.md`, and Pritish confirms it.

| Module | Owner | Commits | PRs that changed it | Git identities (commits) |
|---|---|---|---|---|
| `agents/onboarding/prototype/` | Mousita | 1 | #47, #48 | Claude (1) |
| `agents/onboarding/` | Mousita (0.3.0); Tejas (0.1-0.2) | 13 | #44, #47, #48 | pcpdev (8), MousitaD (3), Claude (2) |
| `agents/supervisor/` | Abhishek | 15 | #5, #31, #59 | pcpdev (14), Claude (1) |
| `agents/critic/` | Abhishek | 10 | #15, #17, #23, #31 | pcpdev (9), Pritish (1) |
| `agents/working-capital/` | Suresh | 8 | — | pcpdev (8) |
| `agents/lendwise/` | Pritish | 12 | #5, #25, #31, #42, #48 | pcpdev (11), Claude (1) |
| `agents/copilot/` | Adesh | 10 | #5, #9, #15, #31, #42, #48, #59 | pcpdev (8), Claude (2) |
| `apps/gateway/` | Abhishek | 89 | #5, #7, #8, #9, #11, #12, #13, #14, #15, #19, #25, #27, #29, #31, #35, #38, #41, #42, #44, #46, #48, #49, #51 | pcpdev (74), Claude (13), Pritish (2) |
| `apps/web/` | Suresh | 49 | #5, #11, #13, #14, #15, #25, #31, #35, #37, #38, #42, #46, #48, #49, #50, #51, #52 | pcpdev (35), Claude (12), Pritish (2) |
| `packages/api-client/` | Suresh | 35 | #11, #13, #14, #15, #25, #27, #31, #35, #38, #42, #48 | pcpdev (30), Claude (3), Pritish (2) |
| `packages/engines/` | Suresh (cash flow); Pritish (loan cost) | 12 | #25, #31, #42, #48 | pcpdev (10), Claude (2) |
| `packages/lender-sim/` | Pritish | 3 | #25, #31 | pcpdev (3) |
| `packages/retrieval/` | Adesh, Tejas | 16 | #7, #15, #19, #31 | pcpdev (16) |
| `packages/observability/` | Abhishek, Pritish | 4 | — | pcpdev (4) |
| `packages/security/` | Abhishek, Pritish | 9 | #5, #13, #27, #31 | pcpdev (9) |
| `packages/core/` | Abhishek, Pritish | 22 | #11, #31 | pcpdev (22) |
| `packages/guardrails/` | Shared (default owner Pritish) | 9 | #5, #8, #9, #13, #31 | pcpdev (9) |
| `packages/llm/` | Shared (default owner Pritish) | 16 | #12, #31, #41, #48 | pcpdev (15), Claude (1) |
| `packages/ledger/` | Shared (default owner Pritish) | 32 | #11, #13, #15, #27, #29, #31, #35, #46, #48 | pcpdev (30), Claude (1), Pritish (1) |
| `packages/tools/` | Shared (default owner Pritish) | 11 | #15, #31 | pcpdev (11) |
| `packages/reports/` | Shared (default owner Pritish) | 2 | — | pcpdev (2) |
| `deploy/` | Suresh | 30 | #5, #7, #8, #11, #12, #15, #27, #29, #31, #32, #33, #37, #41, #46, #48 | pcpdev (23), Claude (7) |
| `data/corpus/` | Tejas, Pritish | 22 | #31 | pcpdev (22) |
| `evaluation/testset/` | Tejas | 3 | — | pcpdev (3) |
| `evaluation/ablations/` | Abhishek | 2 | #8, #31 | pcpdev (2) |
| `evaluation/` | Shared evaluation (Abhishek, Tejas; harness Pritish) | 72 | #1, #5, #7, #8, #9, #10, #11, #12, #15, #16, #18, #20, #22, #23, #26, #28, #31, #34, #36, #39, #46, #48, #49, #51, #55, #56, #57, #58, #59 | pcpdev (59), Claude (10), Pritish (3) |
| `data/` | Shared data (generators, frozen sets) | 26 | #1, #25, #31, #53, #54 | pcpdev (24), Claude (2) |
| `docs/` | Documentation (shared) | 171 | #1, #5, #7, #8, #9, #10, #11, #12, #13, #14, #15, #17, #18, #19, #20, #21, #22, #23, #24, #25, #26, #27, #28, #29, #30, #31, #32, #33, #34, #35, #36, #37, #38, #39, #40, #41, #42, #43, #44, #45, #46, #47, #48, #49, #50, #51, #52, #53, #54, #55, #56, #57, #58, #59 | pcpdev (125), Claude (38), Pritish (7), MousitaD (1) |

A commit that touches several modules counts once in each. PRs are found from their merge commits in the history of `main`; most were merged into `feature/LendWise` and reached `main` through sync PRs (#31, #48, #51, #54, #56), so those sync PRs appear under many modules.
