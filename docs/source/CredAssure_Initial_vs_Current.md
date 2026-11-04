# CredAssure — Initial Draft vs Current Design

**What changed, what stayed, and why**

25 October 2026 · Prepared by Pritish Patil · IIT KGP Capstone, Track B

| | Initial draft | Current design |
| --- | --- | --- |
| **Documents** | FinBridge AI BRD v1.0 + Agentic Workflow Diagram | CredAssure BRD v3.0 (Feasible Scope) + Project Brief v2.0 |
| **Name** | FinBridge AI | CredAssure |
| **Framing** | Agentic workflow for an MSME loan proposal | Track B multi-agent copilot on a hosted ≤8B model, scoped for 4 weeks |

## The short version

The project idea is unchanged: check the preparer, calculate the real funding need, find the truly cheapest offer, and route the proposal to the right human approver. What changed is **how each stage is made trustworthy on a small model, how the result is measured, and how much is built before the deadline.**

## The analogy: from architect's sketch to a house you can move into

The **initial draft** is an architect's concept sketch. It shows every room the family wants — entrance, study, kitchen, living room, front door — and how people walk between them. It is the right house, but nobody could build from it yet: there are no foundations, no wiring plan, and no inspection checklist.

**Version 2.0** is the engineer's construction drawing. The same rooms are there, but it adds what the building inspector (the Track B grading rubric) requires: foundations (a frozen evaluation set and baseline), wiring (retrieval over real regulatory documents), smoke detectors (the Verification Critic and fact ledger) and an inspection log (tracing and failure analysis). It is complete, but it is a mansion: roughly 330 hours of work for a team with about 215.

**Version 3.0** builds the same house in phases. Every room from the sketch is built and usable — nothing is left as an empty plot — but some rooms are finished more simply for now: one negotiation round instead of three, a fixed copilot pipeline instead of a planner. The extensions (rounds 2–3, the planner, delay scenarios) are drawn on the plan with doorways already in place, so they can be added after Gate G3 if time allows.

| In the analogy | In the project |
| --- | --- |
| Architect's sketch | Initial draft: the workflow diagram and BRD v1.0 |
| Construction drawing | BRD v2.0: Track B pillars added |
| Phased build | BRD v3.0: core scope committed, stretch drawn but deferred |
| Rooms | The five gated stages |
| Building inspector | Track B grading: eval set, baseline, RAG, tracing, small-model compensation |
| Smoke detectors | Fact ledger and Verification Critic |
| Extensions with doorways ready | Stretch items, unblocked only after Gate G3 |

## Stage by stage

![Initial draft mapped to current design](images/initial_vs_current.png)

| Stage | Initial draft | Current design | Change | Why |
| --- | --- | --- | --- | --- |
| Start | Employee logs in and initiates a proposal for ₹2 crore | Case created; ₹2 crore stored as an input, never the default amount | Kept, clarified | The diagram's "e.g., ₹2 crore" implied the answer before the analysis |
| 1. Employee readiness | Employee Onboarding Agent: verify identity and role, check training, confirm eligibility; NO-GO loops to onboarding guidance | Readiness Gate (M2): code rule check against HR records, AI explains blockers; case waits and re-runs | Narrowed | Eligibility must be decided by rules, not a small model; onboarding memory and chat are a separate project |
| 2. Funding need | Working Capital Advisory Agent analyses order, cash flows, receivables, payables, inventory | Working Capital Agent (M3): 26-week cash table computed in code, peak shortfall, bridge from ₹2 crore | Kept, hardened | An 8B model cannot be trusted with multi-period arithmetic |
| 3. Lender offers | LendWise: 3 lenders, true cost (APR, fees, insurance), up to 3 negotiation rounds, recommend lowest cost | LendWise (M4): true cost by IRR, hidden-charge check against KFS documents, 1 template negotiation round; rounds 2–3 stretch | Changed | Free-text negotiation was the largest hallucination risk; one round proves the mechanism |
| 4. Proposal | Final Loan Proposal consolidates analysis and evidence | Verification Critic (M5) checks every number and citation, then the report is generated | Added check | Nothing reaches a human unless it traces to the ledger or a cited passage |
| 5. Approval | > ₹1.5 crore → VP Finance; ≤ ₹1.5 crore → Director Finance | > ₹1.5 crore → VP; < ₹1.5 crore → Director; exactly ₹1.5 crore set by configuration (default hold) | Changed | The diagram and BRD v1 disagreed on the boundary |
| Rework | Rejection loops back to LendWise | Return reopens the stage the approver names | Changed | Some rework belongs in Working Capital, not LendWise |
| End | Approved proposal ready for lender submission | Proposal approved; the MSME chooses its lender; no acceptance in the system | Kept | Same human-in-the-loop boundary |

## What was added

None of these appear in the initial draft; all are required by Track B or make the small model safe to use.

| Addition | What it is | Why it was needed |
| --- | --- | --- |
| Code Supervisor | LangGraph state machine that runs stages, enforces gates and step budgets | Gates decided by code cannot be talked past |
| Fact ledger | Store of every validated number with its source | The only place the AI may quote numbers from |
| Verification Critic | Number, citation and banned-content checks before any output reaches a human | Catches hallucinated figures and fabricated sources |
| Ask CredAssure copilot + RAG | Cited answers from 500–600 RBI, MSME, tax, bank-charge and policy documents | Track B's required retrieval pillar |
| Frozen eval set and baseline | 100 items with gold answers; single-prompt baseline with 3 strategies | Proves the system beats a plain prompt |
| Ablations and failure taxonomy | 5 grouped ablations; failures classed as retrieval, reasoning, tool-call or hallucination | Answers the graded question "how did you compensate for a small model?" |
| Tracing and ops | Langfuse Cloud, Docker, rate limiting, caching, demo backup | Track B pillars V and VI |
| Refusal policy | What the copilot refuses: credit scoring, legal advice, offer acceptance | The initial draft said what the system does, not what it must decline |
| Effort plan and gates | ~206 build hours + contingency; four weekly gates with cut rules | Makes the scope finishable and the grade predictable |

## What was removed or deferred

| Item in the initial draft | Status | Reason |
| --- | --- | --- |
| PDF and image documents (OCR, vision fallback) | Removed | Vision model not allowed on the single ≤8B text endpoint; large failure surface |
| Onboarding memory, pending-task recall, onboarding chat | Removed | Effectively the separate "Onboarding Buddy" project |
| Negotiation rounds 2–3 | Deferred to stretch | Core proves the mechanism with one round |
| Copilot that plans its own tool calls | Deferred to stretch | Fixed pipeline is more reliable on a small model |
| Delay scenarios, pause/resume, replay view | Deferred to stretch | Useful, not graded |
| Downloadable PDF proposal pack | Replaced | Markdown/HTML export covers it |
| Cash credit, overdraft, invoice discounting comparison | Removed | Not comparable on one cost metric; copilot can explain them instead |

## What was corrected

| Issue in the initial draft | Correction |
| --- | --- |
| Diagram showed "e.g., ₹2 crore" as the recommended amount | The amount is always calculated; ₹2 crore is only the starting request |
| Diagram used ≤ ₹1.5 crore → Director; BRD v1 held the equal case | Made a configuration value, default hold, with all three settings tested |
| Rejection always looped back to LendWise | Approver names the stage to reopen |
| Personal-loan methodology from the LendWise brief | Business term-loan schema and IRR-based cost; RBI KFS rules confirmed to cover MSME term loans |
| Regulatory references | Updated for RBI's Nov 2025 consolidation into Master Directions and the Income-tax Act, 2025 (s.43B(h) → s.37(2)(g)) |
| Targets as percentages on small samples | Targets as counts (e.g. 15/15), because one miss on 15 items moves a percentage by 6.7 points |

## Open questions from the initial draft: where they stand

| Initial question | Status now |
| --- | --- |
| Q-01 Who approves exactly ₹1.5 crore? | Open — configurable, default hold; recommendation is Director |
| Q-02 Which amount does the threshold apply to? | Resolved — the final validated recommended amount |
| Q-03 Exact preparer qualification criteria | Synthetic rule set for the capstone; real criteria not needed |
| Q-04 Forecast horizon and cash buffer | Resolved — weekly, 26-week default; buffer is a configured policy value |
| Q-05 Which financing types? | Resolved — fixed-schedule working-capital term loans only |
| Q-06 What defines "lowest cost"? | Resolved — effective annual cost (IRR); ties by total ₹ cost, then availability |
| Q-07 Negotiation scope | Resolved — simulated lenders, template messages, fee waiver in core |
| Q-08 Document formats | Resolved — JSON and CSV only |
| Q-09 Does the approver pick the lender? | Resolved — approver approves the proposal; the MSME chooses the lender |

## Targets: then and now

| Measure | Initial draft | Current design |
| --- | --- | --- |
| Cash-flow calculation accuracy | 100% | 15/15 known-answer cases, to ₹1 |
| Cost / APR accuracy | 100% within tolerance | 15/15 cases, to ₹1 and 0.01 pp |
| Lowest-cost offer ranking | ≥95% | 15/15 |
| Policy answers with citations | ≥85% | ≥20/25 with a valid citation |
| Approval routing | 100% below and above | 6/6, including the boundary |
| Pending-task recall across sessions | ≥90% | Dropped with onboarding memory |
| Prompt-injection successes | 0 | 0/8 succeed, plus 20-prompt red-team log |
| Beats a single-prompt baseline | Not measured | Required; ≥92/100 overall |

## What did not change

- Five gated stages in the same order, with GO / NO-GO decisions between them.
- The ₹2 crore request is treated as an input to check, not an answer.
- True cost, not headline rate, decides the lender comparison.
- Approval depends on the validated amount against ₹1.5 crore.
- A human approves; the system never accepts, signs or scores credit.
- Synthetic company, lender and employee data.

## One open recommendation

The Onboarding Agent was narrowed into the Readiness Gate, which makes it read as an agent that disappeared. The recommended fix, not yet applied, is to rename it back to **Employee Onboarding Agent (M2)** and move its guidance loop into core: on NO-GO it produces a cited, personalised checklist of missing training and owners, and re-runs when records update. This restores the initial draft's "guide, complete onboarding, loop back" step for about 5 extra hours.
