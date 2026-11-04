# CredAssure — Project Brief

*An Agentic Framework for Verified MSME Working-Capital Loan Proposals*

Executive Post Graduate Programme in Generative AI and Agentic AI · IIT Kharagpur · Capstone, Track B · 25 October 2026

| | |
| --- | --- |
| **Project** | CredAssure — An Agentic Framework for Verified MSME Working-Capital Loan Proposals |
| **Programme** | Executive Post Graduate Programme in Generative AI and Agentic AI, IIT Kharagpur |
| **Capstone track** | Track B — Multi-Agent Operations Copilot on a hosted ≤8B inference API |
| **Duration** | 4 weeks · 6 members · ~215 person-hours |
| **Domain** | Fintech — MSME working-capital lending |
| **Supporting documents** | Business Requirements Document v3.1; comparison of initial draft and current design |

## Abstract

Micro, Small and Medium Enterprises (MSMEs) often win orders they cannot fund: they must pay for components, labour and logistics weeks before the customer pays. The loan they ask for is usually a rough figure, lender offers hide fees behind headline rates, and the approval route inside the lending organisation depends on the amount. **CredAssure** is a multi-agent system that turns an indicative ₹2 crore request from an electronics MSME into a validated, cost-compared and correctly routed working-capital proposal.

Five gated stages run under a deterministic Supervisor: an **Employee Onboarding Agent** (readiness gate) confirms the preparer is qualified; a **Working Capital Advisory Agent** computes the real funding need from weekly cash flows; a **LendWise Agent** ranks three simulated lender offers by true annual cost and negotiates once; a **Verification Critic** blocks any number or citation not backed by evidence; and approval routing sends the proposal to the Director or VP of Finance. An **Ask CredAssure** copilot answers regulatory and policy questions with citations from a 500–600-document corpus.

The system runs entirely on a hosted model of 8 billion parameters or fewer, without fine-tuning. Its central design claim is that **the AI reads, explains and drafts; code calculates, routes and gates; a human approves.** The claim is tested against a single-prompt baseline and five grouped ablations on a 100-item evaluation set frozen before any agent code is written.

**Team: one agent per member**

| Member | Agent owned end to end | Shared responsibility |
| --- | --- | --- |
| [Name 1] | Supervisor / Orchestrator | Integration lead; approval routing; Streamlit interface; Docker deployment |
| [Name 2] | Employee Onboarding Agent | Evaluation set and gold answers; prompt baseline study |
| [Name 3] | Working Capital Advisory Agent | Cash-flow engine; synthetic MSME cases |
| [Name 4] | LendWise Agent | Loan-cost engine; synthetic lender offers; lender simulator |
| [Name 5] | Verification Critic | Tracing; failure taxonomy; red-teaming; ablation runs |
| [Name 6] | Ask CredAssure copilot | Document corpus and retrieval experiments |

## 1. Problem statement and motivation

A working-capital proposal fails in predictable ways: the wrong amount, the wrong lender, or the wrong approver — and each failure comes from a manual step that no one checks.

### 1.1 The business problem

An electronics manufacturing MSME wins a confirmed ₹3.2 crore order. To deliver it, the business pays for components, assembly labour, testing and logistics over several weeks, while the customer pays roughly two months after delivery. The business is profitable on paper but short of cash in between. Its owner asks the lender's relationship team for ₹2 crore.

A finance employee then prepares the loan proposal. Four problems arise:

| Problem | What goes wrong today | Consequence |
| --- | --- | --- |
| The amount is a guess | ₹2 crore is quoted before anyone models week-by-week cash flow, existing credit lines or customer payment timing | Over-borrowing wastes interest; under-borrowing stalls the order |
| Headline rates hide cost | Processing fees, insurance and upfront deductions are scattered across offer documents | The offer with the lowest advertised rate can be the most expensive overall |
| Approval authority depends on amount | Proposals above ₹1.5 crore need the VP of Finance; below it, the Director | Routing on an unverified number is a governance failure |
| Evidence is not traceable | Figures are copied between spreadsheets and documents by hand | Auditors cannot tell where a number came from |

Indian regulation makes cost transparency a requirement, not a preference: the Reserve Bank of India requires a standardised Key Facts Statement (KFS) for MSME term loans, disclosing the all-in cost including fees. Comparing offers on that basis is exactly the kind of careful, repetitive work that is error-prone when done by hand.

### 1.2 The technical problem

Large language models (LLMs) can read documents, explain findings and draft text, which makes them attractive for this workflow. But this capstone requires a hosted model of **8 billion parameters or fewer, without fine-tuning**. Models of this size are known to fail at multi-period arithmetic, to break structured output on long inputs, to invent plausible-looking citations, and to follow instructions planted inside documents. In lending, each of those failures produces a wrong number in front of a decision-maker.

### 1.3 Research question

> *Can a small hosted language model be made trustworthy enough to support a regulated financial workflow — and which design choices account for the improvement?*

CredAssure answers this with a working system, a frozen evaluation set, a single-prompt baseline and ablations that switch each design choice off in turn.

## 2. Objectives

Each objective has a measurable target on the frozen evaluation set; targets are counts because the categories are small.

| ID | Objective | Measure | Target |
| --- | --- | --- | --- |
| O1 | Only qualified employees can progress a proposal | Readiness cases decided correctly | 10/10 |
| O2 | Derive the funding need from cash flows, not the initial request | Known-answer cash-flow cases correct to ₹1 | 15/15 |
| O3 | Rank lender offers by true cost, not headline rate | Correct lowest-cost ranking | 15/15 |
| O4 | Route every proposal to the correct approver | Routing cases, including the ₹1.5 crore boundary | 6/6 |
| O5 | Answer regulatory and policy questions with real sources | Correct answers with a valid citation | ≥20/25 |
| O6 | Keep unsupported claims and unsafe actions out | Prompt-injection, refusal and isolation cases passed | 19/19 |
| O7 | Beat a single-prompt baseline and explain why | Overall score above best baseline; effect of each design group isolated by ablation | ≥92/100 and above baseline |
| O8 | Keep humans in control | Proposals approved or offers accepted without a human action | 0 |

## 3. Proposed solution

CredAssure splits the proposal into five gated stages, each owned by one agent, and gives every authoritative decision — calculation, gate, route — to code rather than to the model.

![CredAssure in one picture](images/visual_explainer.png)

In the illustrative case, the system shows that the real peak shortfall is ₹1.62 crore in week 9; after a minimum cash buffer and the MSME's unused overdraft, the recommended facility is **₹1.42 crore, not ₹2 crore**. It finds that the lender with the lowest advertised rate is not the cheapest once fees and insurance are counted, confirms every figure in the draft proposal against its source, and routes the ₹1.42 crore proposal to the Director of Finance.

### 3.1 Design principles

| Principle | What it means in practice |
| --- | --- |
| The AI reads, explains and drafts | The model classifies requests, matches document text to offer fields, explains results and writes cited answers |
| Code calculates, routes and gates | Cash flows, loan cost by internal rate of return (IRR), gate decisions and approval routing are deterministic Python, unit-tested |
| Every number has a source | A fact ledger holds every validated figure with its origin; the AI may quote numbers only from it |
| Fail closed | Missing data, failed checks or unsupported claims pause the workflow and ask a human |
| A human decides | A finance approver approves the proposal; the MSME chooses its lender; the system never accepts or signs an offer |

## 4. System architecture and agents

Nine modules sit in five layers: a code Supervisor on top, five AI-assisted agents in the middle, and thirteen deterministic tools underneath that own every number and every gate.

![CredAssure architecture](images/architecture.png)

Agents never call each other. Every hand-off passes through the Supervisor and the fact ledger, which makes each stage testable on its own and every decision traceable.

### 4.1 The agents

| Agent | Job | What the model does | What code does |
| --- | --- | --- | --- |
| **Supervisor / Orchestrator** | Runs the five stages, enforces gates, budgets and routing | Classifies chat input; phrases clarification questions | Every state transition, retry, step and token cap |
| **Employee Onboarding Agent** (readiness gate) | Confirms the preparer may prepare the proposal | Explains blockers in plain language | Checks role, mandatory training, expiry and policy acknowledgement against HR records |
| **Working Capital Advisory Agent** | Finds the real funding need | Explains data problems and cash-gap drivers from ledger facts | 26-week cash table, peak shortfall, recommended amount, bridge from ₹2 crore |
| **LendWise Agent** | Finds the truly cheapest offer | Matches each lender's KFS text to the offer fields to spot hidden charges; selects the negotiation move | Effective annual cost by IRR, ranking, offer versioning, re-audit after negotiation |
| **Verification Critic** | Blocks unsupported content before any human sees it | None in core scope (by design, the model does not check itself) | Number matching against the ledger, citation checks, banned-content checks, report completeness |
| **Ask CredAssure copilot** | Answers rule, policy and case questions at any stage | Writes cited answers from the top-5 retrieved passages; abstains when unsupported | Hybrid retrieval, reranking, case-scoped filtering |

### 4.2 Supporting modules

| Module | Role |
| --- | --- |
| Knowledge and retrieval | Keyword (BM25) and semantic (dense) search over the document corpus, merged by reciprocal-rank fusion and reordered by a reranker |
| Approval routing | Threshold comparison on the validated amount: > ₹1.5 crore to VP, < ₹1.5 crore to Director, equality per configuration |
| Lender simulator | Three fictional lenders with scripted responses, so negotiation results are repeatable |
| Streamlit user interface | Case creation, upload, stage tracker, offer comparison, copilot chat, approval tab |

### 4.3 Technology stack

| Layer | Choice |
| --- | --- |
| Model | Course-provided OpenAI-compatible endpoint, ≤8B instruct model + embeddings endpoint |
| Orchestration | LangGraph typed state machine; Pydantic schemas for every agent output |
| Retrieval | Chroma (dense) + rank_bm25 (sparse), cross-encoder or LLM reranking |
| Calculation | Python `Decimal`; in-house IRR solver (bounded bisection) |
| Storage | SQLite: cases, fact ledger, offers, decisions, append-only audit log |
| Observability | Langfuse Cloud tracing |
| Interface and deployment | Streamlit; Docker Compose; rate limiting and response caching |

## 5. Workflow and user journey

The five stages always run in the same order; a failed gate pauses only that stage, and the case resumes there once the blocker is fixed.

![CredAssure workflow](images/flow_chart.png)

| Gate | Passes when | If it fails |
| --- | --- | --- |
| Readiness | Role, mandatory training and policy acknowledgement are all evidenced | Blockers listed; case waits until HR records are updated, then re-runs |
| Funding need | Inputs are complete and consistent; calculation reproduces from logged inputs | Case pauses with one focused question about the missing or conflicting data |
| Lender comparison | At least two offers are comparable and the ranking is traceable | Corrected offer documents requested |
| Verification | Every number matches the ledger and every citation supports its claim | Returned to the stage that produced the problem |
| Routing | Validated amount compared with ₹1.5 crore | Exactly ₹1.5 crore follows a configurable rule, held for a human by default |

Each agent invocation is capped at 10 steps (LLM or tool calls), as the Track B guidelines require; negotiation rounds are separate invocations.

### 5.1 User journey

The preparer creates the case, uploads data, confirms the funding bridge and submits; CredAssure does the checking, calculating and comparing; one approver decides.

![User journey](images/user_journey.png)

A rejected proposal closes with its reason recorded. A returned proposal reopens only the stage the approver names. The copilot is available at every step.

## 6. Data and knowledge base

Case, lender and employee data is synthetic and generated by seeded code; the retrieval corpus uses real public regulatory and bank documents, so the copilot's citations can be checked against their sources.

![Data flow](images/data_flow.png)

### 6.1 Synthetic datasets

| Dataset | Size | Built with | Deliberately planted cases |
| --- | --- | --- | --- |
| Employee profiles | 20 | Faker (Indian locale) + condition matrix | Expired training, missing record, unauthorised role |
| MSME cases | 15 | Seeded Python; target outcome solved for | Above, below and exactly ₹1.5 crore; need well below ₹2 crore; missing and contradictory fields |
| Lender offers | 45 + revisions | Parameters anchored to public bank charge schedules; instalments from in-house amortisation code | Hidden charges, instalment mismatches, cheapest-rate-but-dearest-overall offers |
| Lender KFS documents | 120–160 | Template in the RBI KFS layout, filled from offer data, numbers re-checked after rendering | Charges missing from the offer record; prompt-injection text |

The model never generates numbers in this data. Gold answers for at least five cash-flow and five offer cases are recomputed by hand in a spreadsheet, independently of the engine code, so the evaluation measures correctness rather than self-consistency.

### 6.2 Retrieval corpus (500–600 documents)

| Collection | Content | Count |
| --- | --- | --- |
| RBI regulation | Current Master Directions on lending, including KFS and fair-practices requirements; repealed circulars excluded | 20–40 |
| Bank charges | Public MSME schedules of service charges from Indian banks and non-banking financial companies | 150–170 |
| MSME and tax law | MSME Development Act provisions on delayed payment, Income-tax Act 2025 s.37(2)(g) (formerly s.43B(h) of the 1961 Act), credit-guarantee (CGTMSE), receivables-discounting (TReDS) and Udyam registration schemes, MSME online dispute resolution portal | 150–170 |
| Synthetic internal | Policies, lender KFS documents, FAQ | 180–250 |

Each document carries source, publisher, effective date and jurisdiction metadata, so superseded or non-Indian rules can be filtered out. Raw third-party files are not committed to the repository; a manifest and download script rebuild the corpus.

## 7. Compensating for a small model

This is the project's main technical contribution: each known weakness of an 8B model is matched to a design choice, and each choice is tested by switching it off.

| Known weakness of small models | Design choice | Ablation that tests it |
| --- | --- | --- |
| Arithmetic drifts over multi-period sums; IRR is guessed, not computed | Code calculators (`Decimal` cash-flow engine, IRR loan-cost engine) | **A1** — the model computes instead |
| Invents or alters numbers in prose; fabricates plausible citations | Fact ledger + Verification Critic (number matching, citation span check, abstention) | **A2** — ledger and Critic off |
| Distracted by irrelevant context; misses exact terms such as section numbers | Hybrid BM25 + dense retrieval, reranker, only top-5 passages in context | **A3** — dense top-5 only |
| Breaks JSON on long inputs; returns GO despite listed blockers | Code-owned gates, enum outputs, schema validation with repair retries, short single-purpose prompts | **A4** — model decides gates in free text |
| Follows instructions planted in documents | Documents passed as delimited untrusted data; routing and tool choice never driven by document text | **A5** — defence off on injection items |

Before any agent code is written, the same model attempts every evaluation item with a single prompt, using three strategies:

| Strategy | Description |
| --- | --- |
| S1 | Structured JSON output with three few-shot examples per category |
| S2 | Chain-of-thought with self-consistency over five samples |
| S3 | Decomposition prompting: extract, compute, decide within one prompt chain |

The team records how the model breaks under each strategy — schema failures, arithmetic errors, wrong gate decisions, invented citations, injection compliance — and those failure patterns justify each design choice above. The final report presents baseline, full-system and ablation scores side by side, per category, and claims an effect only when it appears in more than one category or survives a rerun.

## 8. Evaluation methodology

One 100-item set with gold answers is written and frozen at the end of Week 1, before agent code; every reported score — baseline, ablation and final — comes from this set.

| Category | Items | Scored by | Target |
| --- | --- | --- | --- |
| Regulatory and policy Q&A | 25 | Key-point rubric + citation validity | ≥20 |
| Readiness decisions | 10 | Exact decision and blocker list | 10 |
| Cash-flow and funding need | 15 | Exact numbers, ₹1 tolerance | 15 |
| Offer audit and ranking | 15 | Rank exact; cost to 0.01 percentage points | 15 |
| Negotiation safety | 5 | Allowed move; zero forbidden content | 5 |
| Approval routing | 6 | Exact route, including ₹1.5 crore ± ₹1 | 6 |
| Prompt injection | 8 | No routing change, invented fact or acceptance | 8 |
| Refusal and out of scope | 8 | Correct refusal | 8 |
| Case isolation | 3 | Zero cross-case leakage | 3 |
| End-to-end cases | 5 | Route, amount, recommended offer, report sections | ≥4 |
| **Total** | **100** | | **≥92, and above the best baseline** |

### 8.1 Additional measures

- **Retrieval quality**, measured separately from answer quality: recall@5 and recall@10 (share of queries with a relevant passage in the top 5 or 10) and mean reciprocal rank on 40 labelled queries (target: a relevant passage in the top 5 for at least 34 of 40), across three chunking configurations and four retrieval set-ups (BM25, dense, hybrid, hybrid + reranker).
- **Operational metrics** from traces: task completion rate, average tool calls per task, tokens and median and 95th-percentile latency per stage, Critic fallback rate.
- **Failure taxonomy**: every failed item classed as retrieval miss, reasoning error, tool-call error or hallucination, for both baseline and final system.
- **Judge reliability**: free-text answers use an LLM-as-judge rubric; a 20% human-checked sample reports agreement.

### 8.2 Guarding against a self-graded evaluation

Because the same team builds the data, the engine and the gold answers, three controls keep the evaluation honest: calculation conventions are written down before the engine is coded; gold numbers for ten cases are recomputed by hand independently; and three to four offer cases use structures the engine was not designed around.

## 9. Responsible AI and safety

CredAssure fails closed: whenever data is missing, a check fails, a claim is unsupported or a route is unresolved, the workflow stops and asks a human.

### 9.1 Human-in-the-loop boundary

CredAssure may calculate, compare, draft and recommend. It may not approve a proposal, accept or sign a lender offer, change HR records, score creditworthiness, or route around the approval matrix. No tool or UI control for those actions exists. Every consequential step requires a named human action recorded in an append-only audit log.

### 9.2 Refusal policy

| The copilot refuses or redirects | Response |
| --- | --- |
| Predicting lender approval or giving a credit score | Explains it cannot assess creditworthiness; points to the offer comparison |
| Legal or tax advice on the MSME's position | Cited general information only; recommends a qualified adviser |
| Accepting or signing an offer | Outside the system; directs the user to the approver |
| Overriding a failed gate | Explains the blocker and the action needed |
| Inventing market rates or competing offers | Uses only ledger-backed facts |
| Storing Aadhaar, PAN or bank account numbers | Redacts and explains why |
| Another case's data | States it is not accessible |

### 9.3 Safety controls and tests

| Risk | Control | Test |
| --- | --- | --- |
| Prompt injection via lender documents or corpus | Documents wrapped as delimited untrusted data; tool choice and routing never driven by document text | 8 evaluation items + 20-prompt red-team log |
| Personal data exposure | Pattern and checksum detection before storage, logs and traces | Unit tests; trace search |
| Cross-case leakage | Case-scoped tools and retrieval filters; employee data stored apart from case data | 3 evaluation items |
| Hallucinated figures or sources | Fact ledger + Verification Critic | Zero unsupported claims on safety items |
| Outdated regulation | Effective-date and jurisdiction filters on the corpus | Evaluation items asking which rule applies now |

All company, lender and employee data is synthetic. Lenders are fictional; real bank documents only inform parameter ranges and appear as cited sources.

## 10. Scope

All five stages and the copilot are in the committed core; stretch items deepen them and begin only if the Week 3 gate passes on time.

| Capability | Core (committed) | Stretch (after Week 3 gate) |
| --- | --- | --- |
| Employee Onboarding Agent | Rule check on 20 HR profiles; plain-language blockers | Cited, personalised next-step checklist |
| Working Capital Agent | 26-week cash flow, peak shortfall, bridge from ₹2 crore, recommended amount | Customer payment-delay scenarios |
| LendWise Agent | Three term-loan offers; hidden-charge check; IRR-based true cost; ranking; one fee-waiver negotiation round | Rounds 2–3 with rate-match and tenor moves |
| Verification Critic | Number, citation, banned-content and completeness checks | Model-graded checks of qualitative claims |
| Ask CredAssure copilot | Retrieve → rerank → cited answer; abstains when unsupported | Model plans its own tool calls |
| Retrieval | 500–600 documents; three chunking set-ups; hybrid + reranker | Corpus up to 950 documents |
| Interface and operations | One Streamlit app; Docker; rate limiting; cache; tracing | Pause/resume; evaluator replay view |

**Out of scope:** scanned documents and optical character recognition; live integration with banks, HR or credit bureaus; credit scoring; legal or tax advice; loan application, acceptance or disbursal; real personal or company data; any comparison of cash-credit, overdraft or invoice-discounting products.

## 11. Project plan

Four weekly phases each end in a gate with measurable exit criteria; when a gate is late, scope is cut in a fixed order so the gate itself still closes on time.

![Four-week delivery plan](images/delivery_plan.png)

| Gate | Exit criteria | If late |
| --- | --- | --- |
| G1 — end of Week 1 | 100 evaluation items and 40 retrieval queries frozen with gold answers; synthetic data v1; baseline run with S1–S3; schemas frozen; endpoint limits confirmed | No stretch items for the rest of the project |
| Mid-Week 2 checkpoint | Walking skeleton: mock agents run a case end to end through the Supervisor and user interface | Copilot reduced to retrieval-only answers; negotiation dropped |
| G2 — end of Week 2 | ≥500 documents indexed; retrieval experiments done; calculators pass all known-answer tests; number normaliser tested | Corpus capped at 500; three ablations instead of five |
| G3 — end of Week 3 | Real case traced end to end; Critic blocks planted bad claims; retry and budget paths tested | Feature freeze; Week 4 is evaluation, report and demo only |
| G4 — end of Week 4 | Full evaluation and ablations; failure taxonomy; red-team log; Docker build; report; rehearsed demo with recorded backup | — |

### 11.1 Agent-wise ownership and effort

Each member owns one agent end to end — its prompts, tools, tests and evaluation category — plus one shared workstream. Hours include three per member for the report and demo.

| Member | Agent owned | Agent work | Shared work | Core hours |
| --- | --- | --- | --- | --- |
| [Name 1] | Supervisor / Orchestrator | State machine, gates, step and token budgets, approval routing (17) | Streamlit interface, Docker, rate limiting, caching (15) | 35 |
| [Name 2] | Employee Onboarding Agent | Qualification rules, synthetic HR profiles, explanation prompt (7) | Evaluation set, gold answers, prompt baseline study (26) | 36 |
| [Name 3] | Working Capital Advisory Agent | Agent, input validation, explanation prompts (9) | Cash-flow engine and tests, synthetic MSME cases, MSME and tax documents for the corpus (18) | 30 |
| [Name 4] | LendWise Agent | Agent, hidden-charge matching, negotiation move (9) | Loan-cost engine and tests, synthetic offers and KFS documents, lender simulator (19) | 31 |
| [Name 5] | Verification Critic | Number normaliser, number, citation and content checks (15) | Tracing, red-teaming, ablation runs, failure taxonomy (19) | 37 |
| [Name 6] | Ask CredAssure copilot | Answer pipeline and prompts (5) | Document corpus, chunking and retrieval experiments (29) | 37 |
| **Total** | | | | **206 / ~215 available** |

A further 40 hours of integration and debugging contingency is absorbed by the gate cut rules rather than overtime.

### 11.2 Rules that keep six separate agents working as one system

- **One contract, frozen at Gate G1.** Every agent returns the same result structure (decision, evidence, blockers, output reference) and reads and writes numbers only through the shared fact-ledger functions.
- **Integration lead.** The Supervisor owner runs a walking skeleton with placeholder versions of all five agents by mid-Week 2; each owner then replaces their placeholder with the real agent.
- **Prompts stay with their agent.** Each owner writes and versions their own prompts in a shared registry; the Onboarding Agent owner runs the baseline study across all categories.
- **No one grades their own agent.** The evaluation-set owner hand-computes gold answers for the Working Capital and LendWise cases; agent owners do not write gold answers for their own category.
- **Each owner reports their agent.** The final report has one section per agent: its evaluation category, failures and ablation result.
- **Backup on the riskiest work.** The LendWise cost engine and the Critic's number normaliser start early in Week 2; the Working Capital owner, with the lightest load, backs up LendWise.

## 12. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Evaluation set not frozen by end of Week 1 | Medium | High | Writing starts on day 1; agent code blocked until Gate G1 |
| Engine and gold answers share a misunderstanding | Medium | High | Conventions written first; independent hand-computed checks; cases the engine was not designed around |
| Weak number normalisation (₹1,42,00,000 vs 1.42 crore vs 142 lakh) | High | High | Dedicated normaliser with 50+ format tests; agents write amounts in one canonical format |
| Endpoint limits: small context window, no JSON mode, tight token quota | Medium | High | Limits confirmed on day 2; one offer per call; grouped ablations; response caching |
| PDF extraction garbles tables in bank charge schedules | High | Medium | Extraction tested on 20 documents in Week 1; unreadable documents dropped |
| Superseded or non-Indian documents in the corpus | Medium | Medium | Effective-date and jurisdiction filters; manifest spot checks |
| Integration left to Week 3 | Medium | High | Schemas frozen at G1; walking skeleton by mid-Week 2 |
| Shared endpoint slow during demo week | Medium | Medium | Recorded demo and cached replay of the main case |
| Scope creep | Medium | Medium | Stretch work starts only after G3; cut order fixed in advance |

## 13. Expected outcomes and deliverables

The project delivers a working system and the evidence to judge it: whether a small model, wrapped in the right controls, can support a regulated financial workflow — and which controls matter most.

### 13.1 Deliverables

| Deliverable | Contents | Track B requirement |
| --- | --- | --- |
| Git repository | Full agent stack, calculators with unit tests, evaluation harness, corpus manifest and download script, synthetic data generators | Repository with the full agent stack |
| Running system | Streamlit app in Docker Compose, with rate limiting and caching | Working deployed system |
| Trace dashboard | Langfuse traces of real case and evaluation runs | Trace dashboard |
| Evaluation report | Baseline vs final scores per category, five ablations, retrieval study, failure taxonomy, red-team log | Evaluation report with failure taxonomy |
| Technical report | 12 pages, including the section on compensating for a small model | 12-page technical report |
| Live demo | 10 minutes: one case end to end, a blocked hallucination, a refused request, the evaluation results; recorded backup | 10-minute live demo |

### 13.2 Expected findings

The team expects the baseline to fail most on multi-period arithmetic, gate decisions under missing data and citation accuracy, and expects the largest ablation effects from code calculators (A1) and the fact ledger with Critic (A2). These are hypotheses: the report will state where the results confirm or contradict them.

### 13.3 Beyond the capstone

The pattern — model for language, code for decisions, ledger for evidence, human for approval — transfers to other regulated workflows where small, cheap, privately hosted models are preferred: credit memos, insurance claims triage, procurement approvals and compliance checks.

## 14. Assumptions and open decisions

### 14.1 Assumptions

- The course provides an OpenAI-compatible ≤8B instruct endpoint, an embeddings endpoint and a per-team token quota.
- Synthetic MSME, lender and employee data is acceptable for evaluation; no real personal or company data is used.
- Lender offers are fixed-schedule working-capital term loans, so effective annual cost by IRR is a fair comparison basis.
- The approval threshold applies to the final validated recommended amount, not the initial request or an offer amount.
- Preparer qualification rules are synthetic, representing a typical lender's policy.

### 14.2 Open decisions

| Decision | Current handling | Recommendation | Needed by |
| --- | --- | --- | --- |
| Who approves a proposal of exactly ₹1.5 crore? | Configurable; held for a human by default | Director of Finance, matching the ≤ rule in the original workflow | Before the final demo |
| Endpoint context window, JSON-mode support and rate limits | Designed for a small context and no JSON mode | — | Day 2 of Week 1 |
| Is a locally run reranker or embedding model permitted? | LLM reranking as fallback | Use a local cross-encoder if allowed | End of Week 1 |

## 15. References

1. Executive PG Programme in Generative AI and Agentic AI, IIT Kharagpur — Capstone Project Templates, Track B: *Multi-Agent Operations Copilot on a Hosted ≤8B Inference API*.
2. Reserve Bank of India — instructions on the Key Facts Statement (KFS) for loans and advances, applicable to retail and MSME term loans (2024).
3. Reserve Bank of India — Consolidation of Regulations and Withdrawal of Circulars (November 2025), consolidating earlier circulars into function-wise Master Directions. https://website.rbi.org.in/web/rbi/-/notifications/consolidation-of-regulations-withdrawal-of-circulars
4. Government of India — Micro, Small and Medium Enterprises Development Act, 2006, sections 15–16 (payment to MSME suppliers and delayed-payment interest).
5. Government of India — Income-tax Act, 2025, section 37(2)(g); and Income-tax Act, 1961, section 43B(h), for tax years beginning before 1 April 2026.
6. Ministry of MSME — MSME Online Dispute Resolution portal for delayed-payment cases (from 15 October 2025).
7. Public schedules of service charges for MSME loans published by Indian banks and non-banking financial companies (corpus sources; listed in the project manifest).
8. FinBridge AI Business Requirements Document v1.0 and Agentic Workflow Diagram (initial project draft, 25 October 2026).
9. CredAssure Business Requirements Document v3.1 and Initial Draft vs Current Design comparison.
