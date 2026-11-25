# Contributions

Scope #18 (contribution evidence). One section per member. Each member owns one agent end to end (prompts, tools, tests
and its evaluation category) plus one shared workstream (BRD §5.2). Rule: no member writes the gold answers or reviews the
evaluation items for their own agent.

**How to read the evidence.** Most commits in this repository were made from one machine and one Git identity, so `git
log` authorship does not show who did what. The evidence for each member is the module they own, the progress entries
with their name in `docs/progress/entries/`, and the reviews they signed in `docs/plan/human-review.md`. Each member
writes and signs their own section; nobody writes another member's.

**Owners (set by Pritish, 25 Nov).** Mousita took over the onboarding agent at 0.3.0 (Tejas built 0.1–0.2); Abhishek
owns the Supervisor and the gateway as well as the Critic; Suresh owns the web app and deployment as well as working
capital; Adesh owns the copilot; retrieval is Adesh and Tejas; the corpus is Tejas and Pritish. CODEOWNERS still uses
placeholder handles until each member's GitHub username is added.

**Disclosed exception to the gold-answer rule.** The 3 case-isolation items (T093–T095) were written
by Abhishek on 15 Nov, before he was named owner of the gateway that enforces case scoping. They are decided by code (an
access check answers 403/404, nothing for a model to judge), and the frozen set cannot be re-authored, so the items stay
and this note records it (`evaluation/tests/test_assets.py`).

| Member | Agent owned | Shared workstream | Paths |
|---|---|---|---|
| Abhishek | Supervisor and routing; Verification Critic | FastAPI gateway; number normaliser; tracing; red-teaming; ablations; failure analysis | `agents/supervisor`, `apps/gateway`, `agents/critic`, `packages/observability`, `evaluation/ablations` |
| Mousita | Employee Onboarding (0.3.0) | Onboarding checker design and prototype | `agents/onboarding` |
| Tejas | Employee Onboarding (0.1–0.2) | Test set and gold answers; prompt baseline study; retrieval (with Adesh); corpus (with Pritish) | `evaluation/testset`, `packages/retrieval`, `data/corpus` |
| Suresh | Working Capital Advisory | Cash-flow engine; synthetic MSME cases; web app; deployment | `agents/working-capital`, `packages/engines` (cash flow), `apps/web`, `packages/api-client`, `deploy/` |
| Pritish | LendWise | Loan-cost engine; synthetic offers and KFS; lender simulator; corpus (with Tejas); plan v3.4 delivery (RAI, guardrails, evaluation harness, UI U5–U6, ship) | `agents/lendwise`, `packages/engines` (loan cost), `packages/lender-sim`, `data/corpus`, `docs/progress/modules/rai.md` |
| Adesh | Ask CredAssure copilot | Retrieval (with Tejas); search experiments | `agents/copilot`, `packages/retrieval` |

## Mousita
_To be written by Mousita._ Expected evidence: onboarding 0.3.0 design (PR #43), the stand-alone prototype and its 127
tests (`agents/onboarding/prototype`), the checker that runs beside the rules engine.

## Tejas
_To be written by Tejas._ Expected evidence: onboarding agent 0.1–0.2 (ONB-01..06), retrieval (with Adesh), the corpus
manifest and legal-basis audit (with Pritish), E5 (`evaluation/reports/E5-2026-11-15.md`),
the frozen 100-item test set and gold answers, baseline S1–S3, J1 human labels, human review items assigned in
`docs/plan/human-review.md`.

## Suresh
_To be written by Suresh._ Expected evidence: working-capital agent (WC-01..07), the cash-flow engine and its 15/15
known-answer cases, synthetic MSME cases; the web app (`apps/web` U0–U6, Playwright screenshots and axe results,
Lighthouse scores, H15); deployment (`deploy/`); human review items assigned in `docs/plan/human-review.md`.

## Pritish
- LendWise agent (LW-01..14): KFS charge extraction, offer audit, APR by IRR with GST and CGTMSE, affordability, ranking,
  one fee-waiver negotiation round; loan-cost engine and lender simulator. Extended to three rounds (fee waiver, rate
  match, tenor change) with re-ranking after every counted concession (ADR 0037, LW-15).
- Plan v3.4 phases P0–P5 and P7–P10 on `feature/*` branches and PRs #1–#11 against `feature/LendWise`: retrieval dev
  split, injection design-pattern tests, guardrails package and PII v2, copilot retrieval and span-cited answers,
  evaluation harness and report, security/fairness/safety_v2 draft, RAI UI and U5–U6, ship and RAI documents.
- Evaluation after the plan (19–25 Nov): baseline S1–S3 and the RAG-only and oracle-context rows; Critic diagnostics and
  the K2 quote-grounding fix; red-team runner and live run (25/25 resisted); course-endpoint comparison; final K3 run
  (88/100, A2 38/51); K4 judge calibration against two teammates' labels (kappa 0.789); safety_v2 H24 rule and K5 prep.
- Product work for a non-technical operator (20–24 Nov): plain-language web app, Excel workbook import (ADR 0040), lender
  PDF intake with field-by-field review (ADR 0041), one upload step, lender-file question card; accounts, MFA and
  segregation of duties (ADR 0038, own password per account); case.db on MySQL (ADR 0039); hosted deployment prep and
  `make start`; the implementation gap review (8 fixes); onboarding 0.3.0 built from Mousita's design.
- Documentation and release: system card and model card, demo script, end-to-end test pack and testing guide, user manual
  and walk-through video, CHANGELOG and release checklist for 1.1.0.
- Progress entries: every `docs/progress/entries/*-pritish.md` file (each names its PR, tests and evaluations).

## Abhishek
_To be written by Abhishek._ Expected evidence: the Supervisor (SUP-01..08), approval routing (APR-01..06), the gateway
(API-01, accounts and roles), Verification Critic (VER-01..05), the normaliser suite, E4
(`evaluation/reports/E4-2026-11-16.md`), red-team log, ablations and failure analysis, OWASP/ASI review (H11).

## Adesh
_To be written by Adesh._ Expected evidence: copilot (CP-01..03), retrieval (KR-01..05, with Tejas), retrieval ladder
report.
