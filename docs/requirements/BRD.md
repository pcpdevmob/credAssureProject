# CredAssure — Business Requirements Document

**Agentic framework for verified working-capital loan proposals for an Electronics Manufacturing MSME**

| Document control | Details |
| --- | --- |
| Version | 3.1 |
| Status | Draft for mentor review |
| Date | 26 October 2026 |
| Supersedes | FinBridge AI BRD v1.0 (25 October 2026) |
| Capstone track | IIT Kharagpur Executive PG Programme in Generative AI and Agentic AI, Track B (hosted ≤8B model, no fine-tuning) |
| Business scenario | Electronics manufacturing MSME seeking working-capital finance to fulfil a confirmed ₹3.2 crore customer order |
| Illustrative funding request | ₹2,00,00,000 (₹2 crore); the recommended amount is calculated from validated cash flows |
| Primary users | Proposal preparer; Director, Finance; VP, Finance; evaluator / administrator |
| System components | Supervisor (master agent); Employee Onboarding, Working Capital Advisory, LendWise, Verification Critic and Ask CredAssure agents; Streamlit interface; FastAPI service |

*Updated from FinBridge AI BRD v1.0 to the feasible Track B scope.*

## Index

| Section | Title |
| --- | --- |
| 1 | Executive Summary |
| 2 | Business Context and Problem Statement |
| 3 | Business Objectives and Success Measures |
| 4 | Scope |
| 5 | Stakeholders, User Roles and Team Ownership |
| 6 | System Architecture and Components |
| 7 | Target Business Process and Gates |
| 8 | Functional Requirements |
| 8.1 | User Interface and API |
| 8.2 | Supervisor (Master Agent) |
| 8.3 | Employee Onboarding Agent |
| 8.4 | Working Capital Advisory Agent |
| 8.5 | LendWise Agent |
| 8.6 | Knowledge Retrieval and Ask CredAssure Copilot |
| 8.7 | Verification Critic |
| 8.8 | Approval Routing and Decision Capture |
| 9 | Business Rules |
| 10 | Data Requirements and Synthetic Data |
| 11 | Non-Functional Requirements and Deployment |
| 12 | Prompt Baseline and Small-Model Compensation |
| 13 | Evaluation Plan and Acceptance Criteria |
| 14 | Observability, Safety and Refusal Policy |
| 15 | Delivery Plan, Effort and Gates |
| 16 | Risks and Mitigations |
| 17 | Decisions and Open Questions |
| Appendix A | Illustrative Case and Outputs |
| Appendix B | Changes from Version 1.0 |
| Appendix C | Glossary |

*This index is a navigation guide.*


## 1. Executive Summary

CredAssure (formerly FinBridge AI) is a controlled multi-agent system that prepares and reviews a working-capital loan proposal for an Electronics Manufacturing Micro, Small and Medium Enterprise (MSME). The scenario begins with an indicative ₹2 crore request to fulfil a confirmed ₹3.2 crore customer order. The system does not assume ₹2 crore is correct: it calculates the real funding need from weekly cash flows.

A Supervisor (the master agent), whose decisions are made by code, runs five gated stages in a fixed order. The Employee Onboarding Agent confirms the proposal preparer is qualified. The Working Capital Advisory Agent calculates the funding need. The LendWise Agent compares three simulated lender offers on true annual cost, including fees, GST and guarantee charges, checks that each offer's repayments fit the MSME's cash flow, and runs one negotiation round. The Verification Critic blocks any number or citation that is not backed by evidence. Approval routing then sends the proposal to the right finance approver. Throughout, the Ask CredAssure copilot answers regulatory and policy questions with citations from a 500–600-document library.

The system runs only on a hosted language model of 8 billion parameters or fewer, without fine-tuning, as Track B of the IIT Kharagpur capstone requires. Its design principle is: **the AI reads, explains and drafts; code calculates, routes and gates; a human approves.**

![CredAssure in one picture](images/visual_explainer.png)

> **Approval threshold:** If the final validated loan amount is greater than ₹1.5 crore, the proposal goes to the VP, Finance. If it is below ₹1.5 crore, it goes to the Director, Finance. A proposal of exactly ₹1.5 crore follows a configurable rule; by default it is held for a human decision until the business owner sets the rule.

> **Decision ownership:** Agents recommend and provide evidence. The Supervisor enforces workflow rules. Only the designated human approver can approve the proposal. The system never accepts a lender offer or binds the MSME to a lender; the MSME chooses its lender.

## 2. Business Context and Problem Statement

Electronics manufacturing MSMEs pay for components, labour, testing, packaging and logistics before their customer pays. A large confirmed order can therefore create a temporary cash gap even when the order is profitable. Preparing the loan proposal by hand goes wrong in four predictable ways:

| What goes wrong | Why | Consequence |
| --- | --- | --- |
| The amount is a guess | ₹2 crore is quoted before anyone models week-by-week cash flow, existing credit lines or customer payment timing | Over-borrowing wastes interest; under-borrowing stalls the order |
| Headline rates hide cost | Processing fees, GST, insurance, guarantee fees and upfront deductions sit in separate documents | The lowest advertised rate can be the most expensive offer |
| A cheap loan may not be affordable | Instalments can start before the customer pays | The loan can deepen the cash gap it was meant to close |
| Approval depends on amount | The route changes at ₹1.5 crore | Routing on an unverified number is a governance failure |

Indian regulation makes cost transparency a requirement: the Reserve Bank of India requires a Key Facts Statement (KFS) for MSME term loans, disclosing an annual percentage rate (APR) that includes all charges.

There is also a technical problem. Small language models are known to make arithmetic errors over many periods, break structured output on long inputs, invent plausible-looking citations and follow instructions hidden in documents. CredAssure tests which design choices make a small model trustworthy enough for this workflow. It is a capstone prototype on synthetic company, lender and employee data, not a live lending system.

## 3. Business Objectives and Success Measures

Targets are counts on a 100-item test set frozen before agent code is written, because with small categories one miss moves a percentage sharply.

| ID | Objective | Measure | Target |
| --- | --- | --- | --- |
| OBJ-01 | Only qualified employees progress a proposal | Readiness cases decided correctly | 10/10 |
| OBJ-02 | Derive the funding need from cash flows, not the ₹2 crore request | Known-answer cash-flow cases correct to ₹1 | 15/15 |
| OBJ-03 | Rank offers by true, affordable cost, not headline rate | Correct ranking, including cash-flow fit | 15/15 |
| OBJ-04 | Route every proposal to the correct approver | Routing cases including the ₹1.5 crore boundary | 6/6 |
| OBJ-05 | Answer regulatory and policy questions from real sources | Correct answers with a valid citation | ≥20/25 |
| OBJ-06 | Keep unsupported claims and unsafe actions out | Injection, refusal and data-isolation cases passed | 19/19 |
| OBJ-07 | Beat a single-prompt baseline and explain why | Overall score; effect of each design choice isolated | ≥92/100 and above baseline |
| OBJ-08 | Make every decision traceable | Decisions, calculations and approvals with trace, time and case ID | 100% |
| OBJ-09 | Keep humans in control | Proposals approved or offers accepted without a human | 0 |

## 4. Scope

### 4.1 In scope (committed core)

- One Streamlit user interface backed by a FastAPI service: case creation, data upload, stage tracker, funding analysis, offer comparison, copilot chat, approval inbox and report export.
- Employee Onboarding Agent checking role, mandatory training and policy acknowledgement against 20 synthetic HR profiles.
- Working-capital analysis over 26 weekly periods using order costs, opening cash, receipts, receivables, payables, inventory and existing credit limits.
- Comparison of three simulated fixed-schedule working-capital term-loan offers: APR including GST and guarantee fees, hidden-charge check against each lender's KFS document, repayment-fit check against the cash flow, ranking and one scripted negotiation round.
- Verification Critic, approval routing, append-only audit log and tracing.
- Ask CredAssure copilot with keyword plus semantic search, reranking and citations over 500–600 documents.
- Frozen 100-item test set, single-prompt baseline, five grouped ablations, failure analysis and red-team log.
- Docker deployment with rate limiting and caching.

### 4.2 Stretch (only after the Week 3 gate passes on time)

- Negotiation rounds 2–3 with rate-match and tenor-change moves.
- A copilot that plans its own tool calls.
- Customer payment-delay scenarios in the cash-flow analysis.
- Pause and resume; evaluator replay screen.
- Model-graded checks of qualitative claims in the Critic; cited next-step checklist from the Onboarding Agent.

### 4.3 Out of scope

- Scanned documents, OCR and image inputs.
- Live integration with banks, non-banking lenders, GST, ERP, HR or credit-bureau systems.
- Credit underwriting, credit scores, legal or tax advice, or predictions of lender approval.
- Loan application, sanction, acceptance, signing or disbursal.
- Real employee, customer or company data.
- Cash-credit, overdraft and invoice-discounting price comparison (the copilot may explain these options, without pricing them).

## 5. Stakeholders, User Roles and Team Ownership

### 5.1 User roles

| Role | Can do | Cannot do |
| --- | --- | --- |
| Proposal Preparer | Create a case, upload and correct data, ask the copilot, run stages, submit for approval | Approve own proposal; override a failed gate |
| Director, Finance | Approve, reject or return proposals below ₹1.5 crore | Act on proposals routed to the VP |
| VP, Finance | Approve, reject or return proposals above ₹1.5 crore and held boundary cases | Accept a lender offer through the system |
| Evaluator / Administrator | Run the test set, view traces, maintain synthetic data and the document library | Edit the audit log |

### 5.2 Team ownership: one agent per member

Each member owns one agent end to end (prompts, tools, tests and its test category) plus one shared workstream.

| Member | Agent owned | Shared responsibility |
| --- | --- | --- |
| [Name 1] | Supervisor (master agent) | Integration lead; FastAPI service; approval routing; Streamlit interface; Docker |
| Tejas | Employee Onboarding Agent | Test set and gold answers; prompt baseline study |
| Suresh | Working Capital Advisory Agent | Cash-flow engine; synthetic MSME cases |
| Pritish | LendWise Agent | Loan-cost engine; synthetic lender offers and KFS documents; lender simulator |
| Abhishek | Verification Critic | Number normaliser; tracing; red-teaming; ablations; failure analysis |
| [Name 6] | Ask CredAssure copilot | Document library; search experiments |

Rules for working agent-wise: all agents return one shared result format and use the shared fact-ledger functions, both frozen at the end of Week 1; a working skeleton of all six agents runs by mid-Week 2; and no member writes the gold answers for their own agent's test category.

## 6. System Architecture and Components

Agents never call each other. Every hand-off goes through the Supervisor and a fact ledger that holds each validated number with its source. Thirteen tools written in plain code do every calculation and check.

![CredAssure architecture](images/architecture.png)

| Component | Type | What it does |
| --- | --- | --- |
| Streamlit user interface | Code | Screens for the preparer, the approvers and the evaluator |
| FastAPI service | Code | REST endpoints behind every screen; also used by the test harness |
| Login and roles | Code | Each role sees only its own screens and cases |
| Supervisor (master agent) | AI agent | Runs the stages, enforces gates and budgets, routes to the approver, interprets chat |
| Employee Onboarding Agent | AI agent | Checks role and training; explains blockers |
| Working Capital Advisory Agent | AI agent | Validates case data; explains the funding need |
| LendWise Agent | AI agent | Audits, prices and ranks offers; checks affordability; negotiates once |
| Verification Critic | AI agent | Blocks unsupported numbers and citations |
| Ask CredAssure copilot | AI agent | Answers rule, policy and case questions with citations |
| Cash-flow engine | Code | Weekly cash table, peak shortfall, recommended amount; repayment-fit check for offers |
| Loan-cost engine | Code | APR, total cost and ranking, including GST and guarantee fees |
| Number normaliser and input validators | Code | Reads Indian number formats; checks uploads for missing or conflicting data |
| Fact ledger and audit log | Store | Every validated number with its source; append-only decision history |
| Document ingestion, search and reranker | Code | Builds and searches the document library; filters by date and case |
| Lender simulator and data generators | Code | Scripted lender replies; synthetic employees, cases, offers and KFS documents |
| Test harness and prompt registry | Code | Runs the 100-item test set; versions every prompt |
| Rate limiter, cache, Docker | Code / config | Protects the token quota; one-command start-up |
| Hosted ≤8B model, embeddings endpoint, Langfuse | External services | Language model; text embeddings; tracing |

### 6.1 Key API endpoints

| Endpoint | Purpose |
| --- | --- |
| `POST /cases` | Create a case |
| `POST /cases/{id}/files` | Upload case data |
| `POST /cases/{id}/run` | Start or resume the workflow |
| `GET /cases/{id}` | Status, stage results, blockers, next action |
| `GET /cases/{id}/funding` | Cash table, recommended amount and bridge |
| `GET /cases/{id}/offers` | Offer comparison, affordability flags, negotiation history |
| `POST /cases/{id}/chat` | Ask the copilot about this case |
| `POST /cases/{id}/decision` | Approver's approve, reject or return, with comment |
| `GET /cases/{id}/report` | Proposal report |
| `POST /eval/runs` | Run the test set or an ablation |

## 7. Target Business Process and Gates

Five gated stages run in a fixed order. A failed gate pauses only that stage, and the case resumes there once the blocker is fixed.

![CredAssure workflow](images/flow_chart.png)

| Step | Description | Gate passes when | If it fails |
| --- | --- | --- | --- |
| 1. Create case | Preparer records the MSME, order and indicative ₹2 crore request | — | — |
| 2. Onboarding check | Role, mandatory training and policy acknowledgement checked against HR records | All mandatory rules are evidenced | Blockers listed; case waits, then re-runs |
| 3. Funding need | Weekly cash flow calculated in code; peak shortfall and recommended amount | Inputs complete and consistent; calculation reproduces | One focused question about missing or conflicting data |
| 4. Lender comparison | Offers audited, priced by APR, checked for cash-flow fit, ranked; one negotiation round | At least two comparable offers whose repayments fit the cash flow | Corrected offer documents requested |
| 5. Verification | Every number and citation checked against the ledger and sources | No critical finding | Returned to the stage that caused it |
| 6. Routing | Validated amount compared with ₹1.5 crore | Route determined | Exactly ₹1.5 crore follows the configured rule (default: hold) |
| 7. Decision | Approver approves, rejects or returns to a named stage | Approved | Returned stage reopens; history kept |

Each agent invocation is capped at 10 steps (model or tool calls) and a token budget; negotiation rounds are separate invocations.

## 8. Functional Requirements

Each requirement is tagged **C** (core, committed) or **S** (stretch, only after the Week 3 gate). The **Week** column is the week the requirement is built; it is tested at the gate that closes that week, and again end to end against the frozen test set at Gates G3 and G4. Week 1 builds no features: it produces the specification, test set, synthetic data, baseline and the shared result format every requirement depends on.

### 8.1 User Interface and API

| ID | Requirement | Tag | Week | Acceptance |
| --- | --- | --- | --- | --- |
| UI-01 | Create a case with case ID, MSME, order reference, due date and indicative amount | C | 2 | Indicative amount stored apart from any calculated amount |
| UI-02 | Upload JSON/CSV against published schemas with field-level errors | C | 2 | Invalid file rejected with field, row and reason |
| UI-03 | Stage tracker showing each stage's decision, blockers and next action | C | 2 | Matches Supervisor state |
| UI-04 | Funding view: calculated need beside the ₹2 crore request, with the bridge | C | 3 | Bridge sums exactly to the recommendation |
| UI-05 | Offer view: APR, total cost, net disbursal, affordability and other flags | C | 3 | Non-comparable and unaffordable offers clearly marked |
| UI-06 | Copilot chat scoped to the case, with clickable citations | C | 3 | Every citation opens its source passage |
| UI-07 | Approval inbox: approve, reject or return to a named stage, with comment | C | 3 | Only the routed role can act |
| UI-08 | Report export (Markdown/HTML) with decision history and trace IDs | C | 3 | All report sections present |
| API-01 | Every screen uses the FastAPI endpoints in Section 6.1; the test harness uses the same endpoints | C | 2 | No screen calls agents directly |
| UI-09 | Pause and resume without duplicate stage runs | S | 4 (stretch) | Duplicate runs prevented |
| UI-10 | Evaluator replay screen with trace links | S | 4 (stretch) | One click per stage |

### 8.2 Supervisor (Master Agent)

| ID | Requirement | Tag | Week | Acceptance |
| --- | --- | --- | --- | --- |
| SUP-01 | Fixed plan: Onboarding → Working Capital → LendWise → Critic → Routing | C | 2 | No stage skipped |
| SUP-02 | Classify chat input as copilot question, data correction, approval action or out of scope | C | 3 | Classifier accuracy reported |
| SUP-03 | Run a stage only when upstream gates are GO and inputs pass validation | C | 2 | Forced-GO agent outputs still blocked |
| SUP-04 | Each agent returns a structured result (decision, evidence, blockers, output reference); invalid output repaired up to twice, then ERROR | C | 2 | Failures logged |
| SUP-05 | Re-run deterministic checks on every GO; a failed check overrides the agent | C | 3 | Override logged |
| SUP-06 | On NEEDS_INPUT, pause with one focused question and resume only the blocked stage | C | 3 | Completed stages untouched |
| SUP-07 | Retry failed tools up to twice; enforce 10-step and token caps | C | 3 | Breach ends in ERROR with state saved |
| SUP-08 | Isolate cases: tools receive only the active case ID | C | 3 | 3/3 isolation tests pass |

### 8.3 Employee Onboarding Agent

| ID | Requirement | Tag | Week | Acceptance |
| --- | --- | --- | --- | --- |
| ONB-01 | Load profile and training records from the synthetic HR store | C | 2 | Values never taken from chat |
| ONB-02 | Evaluate the qualification rules: role, mandatory trainings, expiry, policy acknowledgement | C | 2 | Pass, fail or unknown per rule |
| ONB-03 | GO only if all rules pass; NO-GO on any failure; NEEDS_INPUT on a missing record | C | 2 | 10/10 readiness tests |
| ONB-04 | Explain blockers and next actions in plain language | C | 3 | Every failed rule named |
| ONB-05 | Never mark training complete; HR data is read-only | C | 2 | No write tool exists |
| ONB-06 | Reject and redact Aadhaar, PAN and bank account numbers in chat | C | 3 | Redaction tests pass |
| ONB-07 | Personalised next-step checklist citing the relevant policy | S | 4 (stretch) | Citations resolve |

### 8.4 Working Capital Advisory Agent

Recommended facility = peak cumulative shortfall + minimum cash buffer − undrawn credit limits − confirmed mitigations (never below zero), rounded up to ₹1 lakh. All money arithmetic uses exact decimal values.

| ID | Requirement | Tag | Week | Acceptance |
| --- | --- | --- | --- | --- |
| WC-01 | Accept order, costs, opening cash, receipts, receivables, payables, inventory, limits and buffer | C | 2 | Missing field → NEEDS_INPUT naming it |
| WC-02 | Validate dates, units, currency, duplicates, totals and cross-file consistency | C | 2 | Contradictions block GO |
| WC-03 | Weekly cash table over 26 weeks (configurable) | C | 2 | 15/15 known-answer cases to ₹1 |
| WC-04 | Peak shortfall, its week and duration | C | 2 | Shown in the interface and ledger |
| WC-05 | Use offsets only from supplied records | C | 2 | No unsourced offset |
| WC-06 | Bridge from the ₹2 crore request to the recommended amount | C | 2 | Bridge sums exactly |
| WC-07 | Explain drivers (collection delays, inventory build-up, supplier timing) using ledger facts only | C | 3 | Every number matches the ledger |
| WC-08 | Customer payment-delay scenarios (+2 and +4 weeks) | S | 4 (stretch) | Recomputed peak shown |

### 8.5 LendWise Agent

APR is calculated in code from the borrower's actual cash flows: the amount actually received (principal minus upfront fees, GST, insurance and deductions) and every scheduled payment including recurring charges, annualised from the periodic internal rate of return. The team confirms that this matches the RBI KFS calculation method.

| ID | Requirement | Tag | Week | Acceptance |
| --- | --- | --- | --- | --- |
| LW-01 | Accept three offers in a versioned structured format | C | 2 | Invalid offer → NEEDS_INPUT |
| LW-02 | Audit required terms; any missing material term makes the offer non-comparable | C | 2 | Flag shown; offer unranked |
| LW-03 | Cross-check each stated instalment against rate, tenure and amount | C | 2 | Planted mismatches caught |
| LW-04 | Compare each offer with its KFS document; flag charges missing from the offer record | C | 3 | Planted hidden charges caught |
| LW-05 | Calculate amount received, total repayment, total cost and APR | C | 2 | 15/15 known-answer cases (₹1 and 0.01 percentage points) |
| LW-06 | Include GST on every fee and charge (rate configurable, default 18%) | C | 2 | Known-answer cases include GST |
| LW-07 | Include any credit-guarantee fee (e.g. CGTMSE) passed on to the borrower as a recurring charge | C | 2 | Planted guarantee-fee offers priced correctly |
| LW-08 | Price floating-rate offers at the current rate and flag "rate may reset" | C | 2 | Flag on every floating-rate offer |
| LW-09 | Repayment fit: run each offer's repayment schedule through the cash-flow engine; flag any offer that pushes cash below the minimum buffer and never rank it first | C | 3 | Planted cheapest-but-unaffordable offers flagged in all cases |
| LW-10 | Check each offer covers the recommended amount before the peak-shortfall week | C | 3 | Shortfall or late availability flagged |
| LW-11 | Rank comparable, affordable offers by APR; ties broken by total cost, then availability | C | 3 | 15/15 rankings |
| LW-12 | One negotiation round: request a fee waiver citing a verified lower competing fee, from a fixed template | C | 3 | Message passes the Critic |
| LW-13 | Scripted lender simulator returns a new offer version; a concession counts only after re-audit | C | 3 | No unverified concession in any output |
| LW-14 | GO only with at least two comparable, affordable offers; no acceptance capability anywhere | C | 3 | Gate tested with 0–3 such offers |
| LW-15 | Negotiation rounds 2–3 with rate-match and tenor-change moves | S | 4 (stretch) | Three rounds maximum |

### 8.6 Knowledge Retrieval and Ask CredAssure Copilot

| ID | Requirement | Tag | Week | Acceptance |
| --- | --- | --- | --- | --- |
| KR-01 | Compare three ways of splitting documents into passages | C | 2 | recall@5 and recall@10 reported per configuration |
| KR-02 | Combine keyword (BM25) and semantic search with reciprocal-rank fusion | C | 2 | Keyword, semantic and combined compared |
| KR-03 | Rerank the top 30 results to the top 5 | C | 2 | With and without reranking compared |
| KR-04 | Filter by collection, effective date, jurisdiction and case | C | 2 | No superseded or non-Indian rule cited as current |
| KR-05 | Measure retrieval on 40 labelled questions, separately from answer quality | C | 2 | Week 2 report |
| CP-01 | Answer pipeline: classify → retrieve → rerank → answer with passage citations; numbers only from case facts | C | 3 | Critic passes every answer |
| CP-02 | Say "I can't verify that from the available sources" when nothing relevant is found | C | 3 | Abstention tests pass |
| CP-03 | Apply the refusal policy before answering | C | 3 | 8/8 refusal tests |
| CP-04 | Copilot plans its own calls across four tools | S | 4 (stretch) | At most 10 steps per question |

### 8.7 Verification Critic

| ID | Requirement | Tag | Week | Acceptance |
| --- | --- | --- | --- | --- |
| VER-01 | Read every amount, percentage and date in generated text (₹1,42,00,000 / 1.42 crore / 142 lakh / 12% / 0.12) and match it to the ledger | C | 2 | Normaliser passes 50+ format tests |
| VER-02 | Check that every cited passage exists and supports its claim | C | 3 | Fabricated citations blocked |
| VER-03 | Block acceptance language, approval predictions, invented rates, false urgency and personal identifiers | C | 3 | Safety tests pass |
| VER-04 | Check the report has every required section | C | 3 | Missing section blocks the report |
| VER-05 | Allow two regeneration attempts, then fall back to a fixed template | C | 3 | Fallback rate reported |
| VER-06 | Model-graded check of qualitative claims | S | 4 (stretch) | Agreement with human labels reported |

### 8.8 Approval Routing and Decision Capture

| ID | Requirement | Tag | Week | Acceptance |
| --- | --- | --- | --- | --- |
| APR-01 | Amount above ₹1,50,00,000 → VP, Finance | C | 2 | ₹1,50,00,001 routes to the VP |
| APR-02 | Amount below ₹1,50,00,000 → Director, Finance | C | 2 | ₹1,49,99,999 routes to the Director |
| APR-03 | Amount exactly ₹1,50,00,000 → configurable rule: hold (default), Director or VP | C | 2 | All three settings tested |
| APR-04 | Record approver, role, decision, time and comment; decisions cannot be edited | C | 3 | Audit event per decision |
| APR-05 | Return reopens the named stage; a preparer cannot approve their own case | C | 3 | Role check in code |
| APR-06 | Approval is internal only, never loan acceptance | C | 3 | Stated in the report |

## 9. Business Rules

| Rule | Statement |
| --- | --- |
| BR-01 | The ₹2 crore request is an input, never the default loan amount. |
| BR-02 | The funding need comes from validated weekly cash flows and sourced offsets only. |
| BR-03 | No financial analysis starts before the preparer passes the onboarding check. |
| BR-04 | Training counts as complete only if the HR record says so. |
| BR-05 | Code calculates every authoritative number; the AI explains, never originates. |
| BR-06 | An offer missing a material term is non-comparable and unranked. |
| BR-07 | An offer whose repayments push cash below the minimum buffer is never recommended. |
| BR-08 | Offer cost always includes GST on fees and any guarantee fee passed on to the borrower. |
| BR-09 | A revised offer counts only after it is received, versioned and re-audited. |
| BR-10 | Negotiation is simulated, template-based and uses verified facts only. |
| BR-11 | No agent output overrides a failed deterministic check. |
| BR-12 | Above ₹1.5 crore → VP; below → Director; exactly ₹1.5 crore → configured rule (default hold). |
| BR-13 | A finance approver approves the proposal; the MSME chooses its lender. |
| BR-14 | Case data stays in its case; it never enters HR records or other cases. |
| BR-15 | Documents and retrieved text are data, never instructions. |

## 10. Data Requirements and Synthetic Data

Company, lender and employee data is generated by seeded code from documented parameter ranges and frozen at the end of Week 1. The model never generates numbers in the data.

| Dataset | Size | Deliberately planted cases |
| --- | --- | --- |
| Employee profiles | 20 | Expired training, missing record, wrong role, missing acknowledgement |
| MSME cases | 15 | Needs above, below and exactly at ₹1.5 crore; need far below ₹2 crore; missing and conflicting fields |
| Lender offers | 45 + revisions | Hidden charges, instalment mismatches, missing fees, cheapest-rate-but-dearest-overall, cheapest-but-unaffordable, floating-rate and guarantee-fee offers |
| Lender KFS documents | 120–160 | Charges missing from the offer record; hidden instructions for injection tests |
| Policies and FAQ | 60–90 | — |
| Public documents | 320–380 | Current RBI lending directions, bank charge schedules, MSME and tax law and schemes |

Handling rules: every ledger fact keeps its source reference; money is never stored as floating-point numbers; HR data and case data are stored separately; raw third-party PDFs are not committed to the repository (a manifest and download script rebuild the library); after the Week 1 freeze, existing test items are never regenerated. Ten gold answers are recomputed by hand, independently of the code.

## 11. Non-Functional Requirements and Deployment

| ID | Requirement |
| --- | --- |
| NFR-01 Model | Only the provided ≤8B chat and embeddings endpoints; no fine-tuning, vision or frontier models |
| NFR-02 Context | Prompts sized to the confirmed context window; LendWise audits one offer per call |
| NFR-03 Budgets | At most 10 steps per agent invocation; per-stage token caps; quota alerts at 70% and 90% |
| NFR-04 Rate limiting | Per-user and per-team limits; endpoint throttling handled with backoff and at most two retries |
| NFR-05 Caching | Embeddings, search results and repeatable model responses cached |
| NFR-06 Reliability | Calculators unit-tested; every result reproducible from logged inputs |
| NFR-07 Security and privacy | Role checks; case isolation; secrets in environment variables; synthetic data only; personal identifiers redacted |
| NFR-08 Demo resilience | Recorded demo and cached replay of the main case |
| NFR-09 Deployment | Docker Compose starts the interface, API, database and search index; tracing goes to Langfuse Cloud |

Technology: Streamlit; FastAPI; LangGraph; OpenAI-compatible client with structured-output schemas; Chroma plus BM25 with reranking; Python decimal arithmetic; SQLite; Langfuse; pytest.

## 12. Prompt Baseline and Small-Model Compensation

In Week 1, before any agent code, one prompt on the same model attempts all 100 test items using three strategies: structured output with examples (S1), step-by-step reasoning with majority voting over five samples (S2), and breaking the task into sub-questions (S3). The final system must beat the best of these.

| Small-model weakness | Design choice | Ablation |
| --- | --- | --- |
| Arithmetic errors; guessed interest rates | Cash-flow and loan-cost engines in tested code | A1: model calculates instead |
| Invented numbers and citations | Fact ledger plus Verification Critic | A2: ledger and Critic off |
| Distracted by long or irrelevant context | Keyword plus semantic search with reranking; top five passages only | A3: semantic top five only |
| Broken structured output; wrong decisions | Gates decided by code; fixed-choice outputs; schema repair | A4: model decides gates in free text |
| Follows instructions hidden in documents | Documents treated as data; routing never driven by document text | A5: defence off |

Each ablation re-runs only the test categories it affects, to stay within the token quota. An effect is claimed only when it appears in more than one category or survives a rerun.

## 13. Evaluation Plan and Acceptance Criteria

| Category | Items | Target |
| --- | --- | --- |
| Regulatory and policy questions (valid citation) | 25 | ≥20 |
| Onboarding decisions | 10 | 10 |
| Cash-flow and funding need (to ₹1) | 15 | 15 |
| Offer audit, affordability and ranking | 15 | 15 |
| Negotiation safety | 5 | 5 |
| Approval routing, including ₹1.5 crore ± ₹1 | 6 | 6 |
| Prompt injection | 8 | 8 |
| Refusal and out of scope | 8 | 8 |
| Case isolation | 3 | 3 |
| End-to-end cases | 5 | ≥4 |
| **Total** | **100** | **≥92, above the best baseline** |

Also reported: retrieval quality on 40 labelled questions (target: a relevant passage in the top five for at least 34); task completion rate; tool calls, tokens and response time per stage; Critic fallback rate; and a failure classification (search miss, reasoning error, tool error, hallucination) for baseline and final system. Free-text answers are scored by an automated judge, with a 20% human-checked sample reporting agreement.

## 14. Observability, Safety and Refusal Policy

Every case and test item runs under one Langfuse trace, with each agent step, tool call, retry and Critic finding recorded. CredAssure fails closed: missing data, failed checks, unsupported claims or an unresolved route stop the workflow and ask a human.

| The copilot refuses or redirects | Response |
| --- | --- |
| Predicting lender approval or scoring credit | Cannot assess creditworthiness; points to the comparison |
| Legal or tax advice | General cited information only; recommends an adviser |
| Accepting or signing an offer | Outside the system; directs to the approver |
| Overriding a failed gate | Explains the blocker and the action needed |
| Inventing rates or competing offers | Uses verified facts only |
| Storing Aadhaar, PAN or account numbers | Redacts and explains why |
| Another case's data | Not accessible |

Safety tests: 8 prompt-injection items plus a 20-prompt red-team log; personal-identifier redaction tests; 3 case-isolation items; zero unsupported claims on safety items.

## 15. Delivery Plan, Effort and Gates

![Four-week delivery plan](images/delivery_plan.png)

| Gate | Exit criteria | If late |
| --- | --- | --- |
| G1: end of Week 1 | Test set and 40 retrieval questions frozen; synthetic data v1; baseline S1–S3 run; shared result format frozen; endpoint limits known | No stretch items for the rest of the project |
| Mid-Week 2 checkpoint | Working skeleton: placeholder agents run a case end to end through the API and interface | Copilot reduced to retrieval-only answers; negotiation dropped |
| G2: end of Week 2 | At least 500 documents indexed; search experiments done; calculators and number normaliser pass all tests; Onboarding and Working Capital agents work end to end | Library capped at 500; three ablations instead of five |
| G3: end of Week 3 | Real case runs end to end with traces; Critic blocks planted bad claims | Feature freeze; Week 4 is evaluation, report and demo |
| G4: end of Week 4 | Full evaluation and ablations; failure analysis; red-team log; Docker build; report; rehearsed demo | — |

### 15.1 Requirements by week

| Week | Focus | Requirements built | Gate that checks them |
| --- | --- | --- | --- |
| 1 | Specification, test set, synthetic data, baseline, shared result format | None (foundation for all requirements) | G1: test set frozen; baseline scored |
| 2 | Calculators, document search, first agents, skeleton through the API | UI-01–03, API-01; SUP-01, 03, 04; ONB-01–03, 05; WC-01–06; LW-01–03, 05–08; KR-01–05; VER-01; APR-01–03 | G2: retrieval measured; calculators and normaliser pass; Onboarding and Working Capital agents work end to end |
| 3 | LendWise audit and affordability, negotiation, Critic, copilot, approval inbox, tracing | UI-04–08; SUP-02, 05–08; ONB-04, 06; WC-07; LW-04, 09–14; CP-01–03; VER-02–05; APR-04–06 | G3: one real case runs end to end with traces |
| 4 | Full evaluation, ablations, red-teaming, Docker, report, demo; stretch only if G3 passed on time | Stretch: UI-09–10, ONB-07, WC-08, LW-15, CP-04, VER-06 | G4: results final; demo rehearsed |

### 15.2 Effort

| Workstream | Core hours |
| --- | --- |
| Specification, test set, synthetic data, prompt baseline | 42 |
| Document library and retrieval | 35 |
| Calculators, Supervisor, agents, fact ledger, lender simulator (incl. LendWise affordability, GST and guarantee fees) | 63 |
| FastAPI service | 8 |
| Verification Critic and number normaliser | 15 |
| Interface, Docker, rate limiting, caching, tracing | 18 |
| Evaluation runs, ablations, red-teaming | 20 |
| Report and demo | 18 |
| **Build total** | **219** |
| Integration and debugging contingency | 40 |

Capacity is about 215 hours (6 members × 4 weeks × ~9 hours). The plan is slightly over by design: the gate rules decide what is cut, starting with the evaluator replay screen.

## 16. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Test set not frozen by end of Week 1 | No baseline; punctuality marks lost | Writing starts on day 1; no agent code until the freeze |
| Gold answers share the engine's mistakes | Test measures self-consistency, not correctness | Calculation rules written first; ten cases recomputed by hand; offers the engine was not designed around |
| Indian number formats confuse the Critic | Over-blocking or missed wrong numbers | Dedicated normaliser with 50+ format tests; one canonical format in agent output |
| A cheap offer is unaffordable | System recommends a loan the MSME cannot repay on time | Repayment-fit check (LW-09); planted test cases |
| Model endpoint limits | Late redesign | Context window, structured output and quota confirmed on day 2 |
| PDF table extraction fails on charge schedules | Weak hidden-charge detection | 20 documents tested in Week 1; unreadable ones dropped |
| Superseded or non-Indian documents | Copilot cites the wrong rule | Effective-date and jurisdiction filters |
| Six separately built agents fail to integrate | Week 3 breakage | Shared result format frozen in Week 1; skeleton by mid-Week 2 |
| Shared endpoint slow during demo week | Failed live demo | Recorded demo and cached replay |

## 17. Decisions and Open Questions

| Original question (v1.0) | Status |
| --- | --- |
| Q-01 Who approves exactly ₹1.5 crore? | Open: configurable, default hold until the business owner decides |
| Q-02 Which amount does the threshold apply to? | Decided: the final validated recommended amount |
| Q-03 Exact preparer qualification criteria | Synthetic rule set for the capstone |
| Q-04 Forecast horizon and cash buffer | Decided: 26 weekly periods; buffer is a configured policy value |
| Q-05 Which financing types? | Decided: fixed-schedule working-capital term loans |
| Q-06 What defines lowest cost? | Decided: lowest APR among offers whose repayments fit the cash flow; ties by total cost, then availability |
| Q-07 Negotiation scope | Decided: simulated lenders, fixed templates, one fee-waiver round in core |
| Q-08 Document formats | Decided: JSON and CSV only |
| Q-09 Does the approver choose the lender? | Decided: the approver approves the proposal; the MSME chooses its lender |

Questions for the mentor and course staff: whether a code-driven Supervisor satisfies the planner → executor → critic requirement; whether the scope is right-sized; how individual contribution is assessed; what is due at the Week 1 checkpoint; whether a recorded demo is acceptable as backup; the endpoint's context window, structured-output support and token quota; whether a local reranker or embedding model is allowed; whether Langfuse Cloud is acceptable; and whether synthetic data and a code-generated test set are acceptable.

## Appendix A. Illustrative Case and Outputs

An electronics MSME wins a confirmed ₹3.2 crore order and asks for ₹2 crore. Figures below are illustrative and come from synthetic data.

| Stage | Example output |
| --- | --- |
| Onboarding | GO: preparer's role authorised and mandatory training current |
| Working capital | Peak shortfall ₹1.62 crore in week 9; plus ₹10 lakh buffer, less ₹30 lakh unused overdraft; recommended ₹1.42 crore |
| LendWise | Lender A has the lowest headline rate but the highest APR once fees, GST and insurance are included; Lender C's instalments start in month 1 and push cash below the buffer, so it is flagged as unaffordable; Lender B ranks first; Lender A waives part of its fee after one round, re-audited |
| Verification | All figures match the ledger; all citations resolve; no blocked content |
| Routing | ₹1.42 crore is below ₹1.5 crore: routed to the Director, Finance |
| Decision | Director approves; the MSME chooses its lender outside the system |

## Appendix B. Changes from Version 1.0

| Area | Version 1.0 | Version 3.1 |
| --- | --- | --- |
| Name | FinBridge AI | CredAssure |
| Readiness | Onboarding Agent with session memory and pending-task recall | Employee Onboarding Agent: rule check plus plain-language explanation; memory removed |
| Lender offers | Structured, PDF or image input; up to three negotiation rounds; APR "where calculable" | Structured input only; APR always calculated, including GST and guarantee fees; KFS hidden-charge check; repayment-fit check; one round in core |
| Verification | Verification layer | Verification Critic with number normaliser and citation checks |
| New in this version | — | Supervisor as code-driven master agent; fact ledger; Ask CredAssure copilot with 500–600-document library; FastAPI service; frozen test set, baseline and ablations; tracing; refusal policy; effort plan and gates |
| Approval boundary | Diagram said ≤ ₹1.5 crore → Director; text held the equal case | Configurable rule, default hold, all settings tested |
| Rework | Rejection looped back to LendWise | Approver names the stage to reopen |
| Regulatory references | — | Updated for RBI's November 2025 consolidation into Master Directions and the Income-tax Act, 2025 |

## Appendix C. Glossary

| Term | Definition |
| --- | --- |
| MSME | Micro, Small and Medium Enterprise |
| Working capital | Funds used to pay operating costs while waiting for customer payments |
| Peak shortfall | The lowest cumulative cash position below zero across the forecast weeks |
| APR | Annual percentage rate: the yearly cost of a loan including interest and all charges |
| KFS | Key Facts Statement, the RBI-mandated loan cost disclosure for MSME term loans |
| GST | Goods and Services Tax, charged on loan fees |
| CGTMSE | Credit Guarantee Fund Trust for Micro and Small Enterprises |
| Repayment fit | Whether an offer's instalments keep the MSME's cash above its minimum buffer |
| Fact ledger | The store of validated numbers and their sources; the only source the AI may quote |
| Gate | A decision point between stages: GO, NO-GO, NEEDS_INPUT or ERROR |
| Master agent | The Supervisor, which runs all other agents and enforces the workflow |
| Ablation | Re-running the test set with one design choice switched off to measure its effect |
| Simulated lender | A fictional lender with scripted responses, used for testing only |
