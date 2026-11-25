# Contribution map: commits and PRs by module

Generated from `main` at `b3b6657` (2026-11-25) by `scripts/contribution_map.py`.

**Ownership, not authorship.** *Owner* is who is responsible for the module (`.github/CODEOWNERS`, set 25 Nov 2026). *Git identities* is who made the commits. Most of the repository was committed from Pritish's machine (identities `pcpdev` and `Pritish`), so a module's owner may not appear as a commit author. Commits also carry a `Co-authored-by:` trailer for the module owner, counted below as *co-author*. Where a member wrote code that was committed from that machine, they list it in their own signed statement in `CONTRIBUTIONS.md`, and Pritish confirms it.

| Module | Owner | Commits | PRs that changed it | Git identities (commits) |
|---|---|---|---|---|
| `agents/onboarding/prototype/` | Mousita | 1 | #47, #48 | pcpdev (1), Mousita Dhar (1, co-author) |
| `agents/onboarding/` | Mousita (0.3.0); Tejas (0.1-0.2) | 13 | #44, #47, #48 | pcpdev (10), MousitaD (3), Mousita Dhar (2, co-author), Abhishek (1, co-author) |
| `agents/supervisor/` | Abhishek | 15 | #5, #31, #59 | pcpdev (15), Abhishek (4, co-author), Suresh (1, co-author) |
| `agents/critic/` | Abhishek | 10 | #15, #17, #23, #31 | pcpdev (10), Abhishek (3, co-author) |
| `agents/working-capital/` | Suresh | 8 | — | pcpdev (8), Suresh (1, co-author), Abhishek (1, co-author) |
| `agents/lendwise/` | Pritish | 12 | #5, #25, #31, #42, #48 | pcpdev (12), Abhishek (2, co-author) |
| `agents/copilot/` | Adesh | 10 | #5, #9, #15, #31, #42, #48, #59 | pcpdev (10), Adesh (2, co-author), Abhishek (2, co-author) |
| `apps/gateway/` | Abhishek | 90 | #5, #7, #8, #9, #11, #12, #13, #14, #15, #19, #25, #27, #29, #31, #35, #38, #41, #42, #44, #46, #48, #49, #51, #68 | pcpdev (88), Abhishek (31, co-author), Suresh (15, co-author), Adesh (2, co-author), Pritish (2), Mousita Dhar (1, co-author) |
| `apps/web/` | Suresh | 52 | #5, #11, #13, #14, #15, #25, #31, #35, #37, #38, #42, #46, #48, #49, #50, #51, #52, #66, #67, #70 | pcpdev (50), Suresh (35, co-author), Abhishek (4, co-author), Pritish (2) |
| `packages/api-client/` | Suresh | 35 | #11, #13, #14, #15, #25, #27, #31, #35, #38, #42, #48 | pcpdev (33), Abhishek (10, co-author), Suresh (9, co-author), Pritish (2) |
| `packages/engines/` | Suresh (cash flow); Pritish (loan cost) | 12 | #25, #31, #42, #48 | pcpdev (12) |
| `packages/lender-sim/` | Pritish | 4 | #25, #31, #66 | pcpdev (4) |
| `packages/retrieval/` | Adesh, Tejas | 16 | #7, #15, #19, #31 | pcpdev (16), Adesh (5, co-author), Tejas (5, co-author), Suresh (2, co-author) |
| `packages/observability/` | Abhishek, Pritish | 4 | — | pcpdev (4), Abhishek (1, co-author) |
| `packages/security/` | Abhishek, Pritish | 9 | #5, #13, #27, #31 | pcpdev (9), Abhishek (2, co-author) |
| `packages/core/` | Abhishek, Pritish | 22 | #11, #31 | pcpdev (22), Abhishek (3, co-author), Suresh (1, co-author) |
| `packages/guardrails/` | Shared (default owner Pritish) | 9 | #5, #8, #9, #13, #31 | pcpdev (9), Abhishek (2, co-author), Adesh (1, co-author), Suresh (1, co-author) |
| `packages/llm/` | Shared (default owner Pritish) | 16 | #12, #31, #41, #48 | pcpdev (16), Abhishek (3, co-author) |
| `packages/ledger/` | Shared (default owner Pritish) | 32 | #11, #13, #15, #27, #29, #31, #35, #46, #48 | pcpdev (31), Abhishek (7, co-author), Adesh (2, co-author), Tejas (2, co-author), Pritish (1), Suresh (1, co-author) |
| `packages/tools/` | Shared (default owner Pritish) | 11 | #15, #31 | pcpdev (11) |
| `packages/reports/` | Shared (default owner Pritish) | 2 | — | pcpdev (2) |
| `deploy/` | Suresh | 30 | #5, #7, #8, #11, #12, #15, #27, #29, #31, #32, #33, #37, #41, #46, #48 | pcpdev (30), Suresh (12, co-author), Abhishek (2, co-author), Adesh (1, co-author), Tejas (1, co-author) |
| `data/corpus/` | Tejas, Pritish | 22 | #31 | pcpdev (22), Tejas (10, co-author) |
| `evaluation/testset/` | Tejas | 3 | — | pcpdev (3) |
| `evaluation/ablations/` | Abhishek | 2 | #8, #31 | pcpdev (2) |
| `evaluation/` | Shared evaluation (Abhishek, Tejas; harness Pritish) | 81 | #1, #5, #7, #8, #9, #10, #11, #12, #15, #16, #18, #20, #22, #23, #26, #28, #31, #34, #36, #39, #46, #48, #49, #51, #55, #56, #57, #58, #59, #61, #62, #64, #69 | pcpdev (79), Abhishek (3, co-author), Pritish (2), Suresh (2, co-author), Tejas (2, co-author) |
| `data/` | Shared data (generators, frozen sets) | 27 | #1, #25, #31, #53, #54, #65 | pcpdev (27), Tejas (7, co-author) |
| `docs/` | Documentation (shared) | 195 | #1, #5, #7, #8, #9, #10, #11, #12, #13, #14, #15, #17, #18, #19, #20, #21, #22, #23, #24, #25, #26, #27, #28, #29, #30, #31, #32, #33, #34, #35, #36, #37, #38, #39, #40, #41, #42, #43, #44, #45, #46, #47, #48, #49, #50, #51, #52, #53, #54, #55, #56, #57, #58, #59, #60, #61, #62, #63, #64, #65, #66, #67, #68, #69, #70 | pcpdev (188), Suresh (26, co-author), Abhishek (23, co-author), Tejas (7, co-author), Pritish (6), Adesh (3, co-author), Mousita Dhar (2, co-author), MousitaD (1) |

A commit that touches several modules counts once in each. PRs are found from their merge commits in the history of `main`; most were merged into `feature/LendWise` and reached `main` through sync PRs (#31, #48, #51, #54, #56), so those sync PRs appear under many modules.
