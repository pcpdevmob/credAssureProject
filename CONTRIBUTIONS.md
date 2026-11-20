# Contributions

Scope #18 (contribution evidence). One section per member. Each member owns one agent end to end (prompts, tools, tests
and its evaluation category) plus one shared workstream (BRD §5.2). Rule: no member writes the gold answers or reviews the
evaluation items for their own agent.

**How to read the evidence.** Most commits in this repository were made from one machine and one Git identity, so `git
log` authorship does not show who did what. The evidence for each member is the module they own, the progress entries
with their name in `docs/progress/entries/`, and the reviews they signed in `docs/plan/human-review.md`. Each member
writes and signs their own section; nobody writes another member's.

**Still to fill in (owners):** the names for [Name 1] (Supervisor, gateway, deploy), [Name 6] (copilot, retrieval, corpus)
and the UI lead. Until then those rows are placeholders, in this file, `README.md` §1, `docs/build/REPO_STRUCTURE.md`
and `.github/CODEOWNERS`.

| Member | Agent owned | Shared workstream | Paths |
|---|---|---|---|
| [Name 1] | Supervisor and routing | Integration lead; FastAPI gateway; approval routing; Docker | `agents/supervisor`, `apps/gateway`, `deploy/` |
| Tejas | Employee Onboarding | Test set and gold answers; prompt baseline study | `agents/onboarding`, `evaluation/testset` |
| Suresh | Working Capital Advisory | Cash-flow engine; synthetic MSME cases | `agents/working-capital`, `packages/engines` (cash flow) |
| Pritish | LendWise | Loan-cost engine; synthetic offers and KFS; lender simulator; plan v3.4 delivery (RAI, guardrails, evaluation harness, UI U5–U6, ship) | `agents/lendwise`, `packages/engines` (loan cost), `packages/lender-sim`, `docs/progress/modules/rai.md` |
| Abhishek | Verification Critic | Number normaliser; tracing; red-teaming; ablations; failure analysis | `agents/critic`, `packages/observability`, `evaluation/ablations` |
| [Name 6] | Ask CredAssure copilot | Document library; search experiments | `agents/copilot`, `packages/retrieval`, `data/corpus` |
| UI lead (to name) | — | React web app and generated client | `apps/web`, `packages/api-client` |

## [Name 1]
_To be written by the member: what you built, decisions you made, evaluations you ran, reviews you signed._

## Tejas
_To be written by Tejas._ Expected evidence: onboarding agent (ONB-01..06), E5 (`evaluation/reports/E5-2026-11-15.md`),
the frozen 100-item test set and gold answers, baseline S1–S3, J1 human labels, human review items assigned in
`docs/plan/human-review.md`.

## Suresh
_To be written by Suresh._ Expected evidence: working-capital agent (WC-01..07), the cash-flow engine and its 15/15
known-answer cases, synthetic MSME cases, human review items assigned in `docs/plan/human-review.md`.

## Pritish
- LendWise agent (LW-01..14): KFS charge extraction, offer audit, APR by IRR with GST and CGTMSE, affordability, ranking,
  one fee-waiver negotiation round; loan-cost engine and lender simulator.
- Plan v3.4 phases P0–P5 and P7–P10 on `feature/*` branches and PRs #1–#11 against `feature/LendWise`: retrieval dev
  split, injection design-pattern tests, guardrails package and PII v2, copilot retrieval and span-cited answers,
  evaluation harness and report, security/fairness/safety_v2 draft, RAI UI and U5–U6, ship and RAI documents.
- Progress entries: every `docs/progress/entries/*-pritish.md` file.

## Abhishek
_To be written by Abhishek._ Expected evidence: Verification Critic (VER-01..05), the normaliser suite, E4
(`evaluation/reports/E4-2026-11-16.md`), red-team log, ablations and failure analysis, OWASP/ASI review (H11).

## [Name 6]
_To be written by the member._ Expected evidence: copilot (CP-01..03), retrieval (KR-01..05), the corpus manifest and
legal-basis audit, retrieval ladder report.

## UI lead
_To be written by the member._ Expected evidence: `apps/web` U0–U6, Playwright screenshots and axe results, Lighthouse
scores (H15).
