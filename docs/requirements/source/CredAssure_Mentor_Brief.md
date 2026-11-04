# CredAssure — Project Brief

*Agentic, verified working-capital loan proposals for MSMEs · IIT Kharagpur Capstone, Track B · 26 October 2026*

## Problem and solution

**Problem.** An electronics MSME with a confirmed ₹3.2 crore order asks a lender for ₹2 crore of working capital. That figure is a guess, lender offers hide fees behind headline rates, and the internal approver depends on the amount (above ₹1.5 crore: VP Finance; below: Director Finance). Preparing the proposal by hand risks the wrong amount, the wrong lender and the wrong approver.

| What goes wrong | Why | Consequence |
| --- | --- | --- |
| The amount is a guess | ₹2 crore is quoted before anyone models week-by-week cash flow, existing credit lines or customer payment timing | Over-borrowing wastes interest; under-borrowing stalls the order |
| Headline rates hide cost | Processing fees, insurance and upfront deductions sit in separate offer documents | The lowest advertised rate can be the most expensive offer |
| Approval depends on amount | The route changes at ₹1.5 crore | Routing on an unverified number is a governance failure |
| Figures are not traceable | Numbers are copied between spreadsheets by hand | Reviewers cannot tell where a figure came from |

**Solution.** CredAssure is a multi-agent system that checks the preparer is qualified, calculates the real funding need, finds the truly cheapest offer, verifies every claim and routes the proposal to the right approver — using only a hosted model of 8 billion parameters or fewer, with no fine-tuning.

**Core idea.** The AI reads, explains and drafts. Code calculates, routes and gates. A human approves.

**Why this is technically hard.** The course limits us to a small hosted model. Models of this size are known to make arithmetic errors over many periods, break structured output on long inputs, invent plausible-looking citations and follow instructions hidden inside documents. In lending, each of those puts a wrong number in front of a decision-maker. Our research question is which design choices make a small model trustworthy enough for this workflow — and we will measure the answer, not assume it.

## How it works

Five gated stages run in a fixed order; each must pass before the next starts, and a failure pauses only that stage.

![CredAssure in one picture](images/visual_explainer.png)

In the example, the real need is **₹1.42 crore, not ₹2 crore**, the lowest headline rate is not the cheapest offer once fees are counted, and the proposal goes to the Director of Finance.

### Workflow and gates

![CredAssure workflow](images/flow_chart.png)

| Gate | Passes when | If it fails |
| --- | --- | --- |
| Onboarding | Role, mandatory training and policy acknowledgement are on record | Blockers listed; case waits until records are updated |
| Funding need | Inputs are complete and consistent; the calculation reproduces | One focused question about the missing or conflicting data |
| Lender comparison | At least two offers are comparable and their repayments fit the cash flow | Corrected offer documents requested |
| Verification | Every number matches its source; every citation supports its claim | Sent back to the stage that caused the problem |
| Routing | Validated amount compared with ₹1.5 crore | Exactly ₹1.5 crore is held for a human decision (configurable) |

The approver can approve, reject, or return the proposal to a named stage. The system never accepts or signs a lender offer; the MSME chooses its lender.

## Agents and owners

Each member owns one agent end to end, plus one shared workstream.

| Agent | What it does | Owner | Shared work |
| --- | --- | --- | --- |
| Supervisor | Runs the stages, enforces gates and routes to the approver | [Name 1] | Integration, interface, deployment |
| Employee Onboarding Agent | Confirms the preparer's role and training | [Name 2] | Evaluation set, prompt baseline |
| Working Capital Agent | Calculates the real funding need from weekly cash flows | [Name 3] | Cash-flow engine, synthetic MSME data |
| LendWise Agent | Ranks three offers by true cost (including GST and guarantee fees), checks repayments fit the cash flow, negotiates once | [Name 4] | Loan-cost engine, synthetic lender data |
| Verification Critic | Blocks any number or citation without a source | [Name 5] | Tracing, red-teaming, ablations |
| Ask CredAssure copilot | Answers rule and policy questions with citations | [Name 6] | Document corpus, retrieval experiments |

Stack: LangGraph, Streamlit, SQLite, Chroma with keyword search, Langfuse tracing, Docker.

### Architecture

Agents never call each other: every hand-off goes through the Supervisor and a fact ledger that holds each validated number with its source. Thirteen tools written in plain code do all calculations and checks.

![CredAssure architecture](images/architecture.png)

### Design choices that compensate for a small model

| Small-model weakness | Our design choice |
| --- | --- |
| Arithmetic errors; guessed interest rates | Funding need and loan cost (internal rate of return) computed in tested Python code |
| Invented numbers and citations | Fact ledger as the only source of numbers; Verification Critic checks every figure and citation |
| Distracted by long or irrelevant context | Keyword plus semantic search with reranking; only the top five passages reach the model |
| Broken structured output; wrong decisions | Gates decided by code; fixed-choice outputs; schema checks with retries |
| Follows instructions hidden in documents | Documents treated strictly as data; routing never driven by document text |

Each choice is tested by switching it off and re-running the test set.

**Affordability, not just price.** A loan whose instalments start before the customer pays can deepen the very cash gap it is meant to close. LendWise therefore runs every offer's repayment schedule through the cash-flow engine and never recommends an offer that pushes cash below the minimum buffer, however cheap it is. Offer cost also includes GST on fees and any credit-guarantee fee, and floating-rate offers are flagged.

## System components end to end

Everything the team builds or connects to, from the screen down to the external model, grouped by layer. Six components are AI agents; the rest are plain code, data stores or external services.

| Layer | Component | Type | What it does |
| --- | --- | --- | --- |
| Front end | Streamlit user interface | Code | Screens for the preparer, the approver and the evaluator (listed below) |
| API | FastAPI backend | Code | REST endpoints behind every screen; also used by the evaluation harness |
| API | Login and roles | Code | Preparer, Director, VP and evaluator roles; each sees only their screens and cases |
| Orchestration | Supervisor (master agent) | AI agent | Runs the stages, enforces gates and budgets, routes to the approver, handles chat |
| Agents | Employee Onboarding Agent | AI agent | Checks the preparer's role and training; explains blockers |
| Agents | Working Capital Agent | AI agent | Validates case data; explains the funding need |
| Agents | LendWise Agent | AI agent | Audits and ranks offers; runs one negotiation round |
| Agents | Verification Critic | AI agent | Blocks unsupported numbers and citations before any human sees them |
| Agents | Ask CredAssure copilot | AI agent | Answers rule, policy and case questions with citations |
| Calculation | Cash-flow engine | Code | Weekly cash table, peak shortfall, recommended amount |
| Calculation | Loan-cost engine | Code | True annual cost by internal rate of return, total cost, ranking |
| Calculation | Number normaliser | Code | Reads ₹1,42,00,000, 1.42 crore and 142 lakh as the same value |
| Calculation | Input validators | Code | Checks uploaded files for missing fields, wrong units and conflicts |
| Evidence | Fact ledger | Code + store | Every validated number with its source; the only source the AI may quote |
| Evidence | Audit log | Store | Append-only record of every decision, edit and approval |
| Retrieval | Document ingestion | Code | Downloads, extracts and splits documents; records source and date |
| Retrieval | Hybrid search and reranker | Code | Keyword plus semantic search; reorders results; filters by date and case |
| Simulation | Lender simulator | Code | Three fictional lenders with scripted negotiation replies |
| Simulation | Synthetic data generators | Code | Employee profiles, MSME cases, lender offers and offer documents |
| Quality | Evaluation harness | Code | Runs the 100-item test set against the API; scores baseline, system and ablations |
| Quality | Prompt registry | Code | Versioned prompts for every agent |
| Operations | Rate limiter and cache | Code | Protects the shared token quota; reuses repeated model and search calls |
| Operations | Docker Compose | Config | Starts the interface, API, database and search index with one command |
| Storage | SQLite | Store | Cases, offers, decisions, ledger, audit log |
| Storage | Chroma and keyword index | Store | Document passages for search |
| External | Hosted ≤8B chat endpoint | External API | The only language model used |
| External | Embeddings endpoint | External API | Turns passages and questions into vectors for semantic search |
| External | Langfuse Cloud | External API | Traces every agent step, tool call and model call |

### User interface screens

| Screen | Used by | What it shows or does |
| --- | --- | --- |
| Case setup | Preparer | Create a case: MSME, order, due date, indicative amount |
| Readiness | Preparer | Onboarding result and any blockers |
| Data upload | Preparer | Upload case files; see and fix flagged fields |
| Funding analysis | Preparer | Weekly cash table, peak shortfall, bridge from ₹2 crore to the recommended amount |
| Offer comparison | Preparer | Offers side by side: true cost, total cost, flags, negotiation result |
| Stage tracker | Preparer, approver | Status of every stage, blockers and next action |
| Copilot chat | Preparer | Questions answered with clickable citations |
| Approval inbox | Director, VP | Proposal review; approve, reject or return to a named stage, with comment |
| Report | All | Proposal report export with decision history |
| Evaluation view (stretch) | Evaluator | Test-set runs, scores and links to traces; results are also available from the test harness |

### Backend API

| Endpoint | Purpose |
| --- | --- |
| `POST /cases` | Create a case |
| `POST /cases/{id}/files` | Upload case data files |
| `POST /cases/{id}/run` | Start or resume the workflow from the current stage |
| `GET /cases/{id}` | Case status, stage results, blockers and next action |
| `GET /cases/{id}/funding` | Cash table, recommended amount and bridge |
| `GET /cases/{id}/offers` | Offer comparison and negotiation history |
| `POST /cases/{id}/chat` | Ask the copilot a question about this case |
| `POST /cases/{id}/decision` | Approver's approve, reject or return, with comment |
| `GET /cases/{id}/report` | Proposal report |
| `POST /eval/runs` | Run the test set or an ablation; returns scores |
| `GET /health` | Service and endpoint status |

The API layer adds about 8 hours and is owned by the Supervisor owner as part of integration. It lets each agent owner test their agent through the same endpoints the interface uses, and keeps the interface replaceable later.

## Data

Company, lender and employee data is synthetic and generated by code, so every test case has a known correct answer. The document library uses real public sources, so the copilot's citations can be checked.

| Dataset | Size | Purpose |
| --- | --- | --- |
| Employee profiles | 20 | Qualified, expired-training, missing-record and wrong-role cases |
| MSME cases | 15 | Funding needs above, below and exactly at ₹1.5 crore; missing and conflicting data |
| Lender offers | 45 + revisions | Hidden charges, instalment mismatches, cheapest-rate-but-dearest-overall offers, cheapest-but-unaffordable offers, floating rates |
| Document library | 500–600 | Current RBI lending directions, bank charge schedules, MSME and tax law, synthetic internal policies |

The model never generates numbers in the data, and ten gold answers are recomputed by hand to catch errors shared by the code and the test set.

## How we measure success

A 100-item test set with known correct answers is frozen in Week 1, before any agent code. It scores three things: a single-prompt baseline on the same model, the full system, and the system with each design choice switched off in turn — which shows what actually compensates for a small model.

| Area | Target |
| --- | --- |
| Funding-need and loan-cost calculations | 30/30 exact |
| Approver routing, including the ₹1.5 crore boundary | 6/6 |
| Regulatory answers with a valid citation | ≥20/25 |
| Prompt-injection, refusal and data-isolation cases | 19/19 |
| Overall | ≥92/100 and above the baseline |

The baseline tries three prompting styles: structured output with examples, step-by-step reasoning with majority voting, and breaking the task into sub-questions. We also report:

- **Search quality on its own:** how often a relevant passage appears in the top five results for 40 labelled questions, across three ways of splitting documents and four search set-ups.
- **Failure types:** every wrong answer classed as a search miss, a reasoning error, a tool error or a hallucination.
- **Cost and speed:** tool calls, tokens and response time per stage, from traces.

## Four-week plan

| Week | Focus | Gate at end of week |
| --- | --- | --- |
| 1 | Specification, test set, synthetic data, baseline, shared result format | Test set frozen; baseline scored |
| 2 | Calculators (including GST and guarantee fees), number normaliser, document search, Onboarding and Working Capital agents, skeleton of all agents through the API | Retrieval measured; calculators and normaliser pass all tests; Onboarding and Working Capital agents work end to end |
| 3 | LendWise audit, affordability check and negotiation; Verification Critic; copilot; approval inbox; tracing | One real case runs end to end |
| 4 | Full evaluation, ablations, red-teaming, Docker, report, demo; stretch only if the Week 3 gate passed | Results final; demo rehearsed |

Effort is ~219 hours, including the API layer and LendWise's cash-flow checks, against ~215 available. If a gate slips, extras are dropped (extra negotiation rounds, copilot planning), never the gate. Every requirement in the BRD carries the week it is built, so this plan and the BRD follow the same schedule.

### Scope

| Committed | Added only if Week 3 finishes on time | Out of scope |
| --- | --- | --- |
| All five stages and the copilot; one negotiation round; 500–600 documents; Streamlit interface and FastAPI backend in Docker | Negotiation rounds 2–3; copilot that plans its own tool calls; payment-delay scenarios; pause and resume | Scanned documents; live bank or HR systems; credit scoring; loan acceptance; real personal data |

Agents plug into one shared result format and the fact ledger, both fixed at the end of Week 1, and a working skeleton of all six runs by the middle of Week 2.

## Top risks

| Risk | Mitigation |
| --- | --- |
| Test set late in Week 1 | Writing starts on day 1; no agent code until it is frozen |
| Gold answers share the engine's mistakes | Calculation rules written before coding; ten cases recomputed by hand |
| Indian number formats confuse the Critic (₹1,42,00,000 vs 1.42 crore vs 142 lakh) | Dedicated number normaliser with 50+ format tests; agents write amounts in one format |
| Model endpoint limits (context size, structured output, token quota) | Confirmed on day 2; prompts kept short; results cached; ablations grouped |
| Six separately built agents fail to fit together | Shared result format fixed in Week 1; working skeleton by mid-Week 2 |
| Shared endpoint slow during demo week | Recorded demo and cached replay as backup |

## Questions for the mentor

**Design and scope**

1. Does a Supervisor whose decisions are made by code satisfy Track B's planner → executor → critic requirement, or do evaluators expect the model itself to plan?
2. Is the scope right-sized — five agents plus a copilot — or would you prefer fewer agents built in more depth?

**Grading and submission**

3. With one agent per member, how is individual contribution assessed?
4. What exactly is due at the end-of-Week-1 checkpoint: the test set file, the baseline report, or both?
5. If the shared endpoint is slow on demo day, is a recorded demo acceptable as a backup?

**Technical constraints**

6. What are the endpoint's context window, structured-output support and team token quota?
7. Is a locally run reranker or embedding model allowed alongside the provided endpoint?
8. Is an external tracing service (Langfuse Cloud) acceptable, or must everything run locally?

**Data and evaluation**

9. Is synthetic company and lender data acceptable for the final evaluation?
10. Can the test set be partly generated by code, or must the gold answers be written by hand?
11. Is it acceptable to use the same small model as an automated judge for free-text answers, checked against a 20% human-reviewed sample?
