# FINBRIDGE AI — Business Requirements Document

**Agentic workflow for working-capital financing for an Electronics Manufacturing MSME**

| **Document control** | **Details** |
|---|---|
| Version | 1.0 |
| Status | Draft for review |
| Date | 25 October 2026 |
| Business scenario | Electronics manufacturing MSME seeking working-capital finance to fulfil a customer order |
| Illustrative funding request | ₹2,00,00,000 (₹2 crore); final requirement to be calculated from validated cash-flow data |
| Primary users | Proposal preparer / relationship or finance advisor; Director of Finance; VP Finance; system administrator |
| System components | Employee Onboarding Agent; Working Capital Advisory Agent; LendWise Agent; UI; Supervisor/Orchestrator and rule-based controls |

*Prepared from the three supplied project briefs and the FinBridge AI concept.*

---

## Index

| **Section** | **Title** |
|---|---|
| 1 | Executive Summary |
| 2 | Business Context and Problem Statement |
| 3 | Business Objectives and Success Measures |
| 4 | Scope |
| 5 | Stakeholders and User Roles |
| 6 | Target Business Process |
| 7 | Functional Requirements |
| 7.1 | User Interface and Case Management |
| 7.2 | Employee Onboarding Agent |
| 7.3 | Working Capital Advisory Agent |
| 7.4 | LendWise Agent |
| 7.5 | Supervisor / Orchestrator and GO/NO-GO Gates |
| 7.6 | Approval Routing and Decision Capture |
| 7.7 | Verification, Audit and Reporting |
| 8 | Business Rules |
| 9 | Data Requirements and Document Handling |
| 10 | Non-Functional Requirements |
| 11 | Exception Handling |
| 12 | Acceptance Criteria and Evaluation |
| 13 | Assumptions, Dependencies and Constraints |
| 14 | Risks and Mitigations |
| 15 | Implementation Approach and Deliverables |
| 16 | Open Questions / Decisions Required |
| Appendix A | Illustrative Case and Outputs |
| Appendix B | Glossary |

---

## 1. Executive Summary

FinBridge AI is a controlled agentic workflow that supports preparation and review of a working-capital loan proposal for an Electronics Manufacturing Micro, Small and Medium Enterprise (MSME). The business scenario begins with an indicative ₹2 crore financing request to fulfil a customer order. The system must not assume that ₹2 crore is the correct loan amount: the Working Capital Advisory Agent will calculate the funding gap from validated cash-flow and operating data.

The workflow contains three specialist agents and a user interface, coordinated by a Supervisor/Orchestrator. The Employee Onboarding Agent checks whether the proposal preparer has completed the required onboarding, training and task-specific prerequisites. If the employee is qualified, the Working Capital Advisory Agent assesses the cash-flow need. The LendWise Agent then audits and compares offers from three simulated lenders, including all relevant fees and charges, and may conduct up to three rounds of simulated negotiation. A verification layer checks evidence and calculations before the proposal is routed for human approval.

> **Approval threshold:** If the final validated loan amount is greater than ₹1.5 crore, route the proposal to the VP, Finance. If the amount is below ₹1.5 crore, route it to the Director, Finance. A request exactly equal to ₹1.5 crore is not specified in the business instruction and must be confirmed before implementation. Until clarified, the system must pause and request a routing decision.

> **Decision ownership:** Agents may recommend GO or NO-GO and provide evidence. The Supervisor enforces workflow rules. Only the designated human approver can approve the proposal; the system must never submit a loan acceptance or bind the MSME to a lender offer.

---

## 2. Business Context and Problem Statement

Electronics manufacturing MSMEs may incur material, component, labour, production, testing, packaging and logistics costs before collecting payment from their customer. A large confirmed order can create a temporary cash-flow gap even when the order is commercially viable. The company needs a disciplined process to estimate the actual short-term funding requirement, compare financing offers on a consistent basis, and route the proposal to the correct finance authority.

The current project aims to reduce manual effort and improve consistency by joining three capabilities: employee readiness, business cash-flow assessment, and evidence-based lender-offer comparison. It is a capstone prototype using synthetic company and lender data, not a live lending or credit-approval system.

---

## 3. Business Objectives and Success Measures

| **ID** | **Objective** | **Proposed measure** |
|---|---|---|
| OBJ-01 | Ensure only appropriately prepared employees can prepare or progress a proposal. | No proposal advances past the readiness gate when mandatory prerequisites are unmet. |
| OBJ-02 | Calculate the actual funding requirement rather than accepting the initial ₹2 crore request without validation. | 100% accuracy on a frozen set of deterministic cash-flow calculation tests. |
| OBJ-03 | Compare three financing offers using total cost and verified terms, not advertised interest rate alone. | 100% calculation accuracy within defined rounding tolerance; ≥95% correct best-offer selection on fully specified test cases. |
| OBJ-04 | Prevent unsupported financial claims and unverified loan terms from entering the proposal. | Zero unsupported material financial claims in the frozen safety test set. |
| OBJ-05 | Route proposals according to the loan-amount approval threshold. | 100% correct routing for test amounts below and above ₹1.5 crore; boundary case blocked pending policy clarification. |
| OBJ-06 | Make decisions traceable and reviewable. | Every agent decision, calculation, blocker, revision and approval is logged with timestamp and case ID. |
| OBJ-07 | Keep the process human-controlled. | No loan offer is accepted and no final proposal is approved without the required human action. |

---

## 4. Scope

### 4.1 In Scope

- A single UI for case creation, employee readiness status, financial document upload, lender-offer comparison, workflow status and proposal review.
- Employee onboarding and task-specific qualification checks based on the Employee Onboarding Buddy brief.
- Working-capital requirement analysis using cash-flow forecasts and relevant operating/financial information, including receivables, payables, inventory, opening cash, customer-order costs and existing facilities where available.
- Processing of structured CSV/Excel/JSON data and supported PDF/image documents, with extracted values linked to source evidence.
- Comparison of three simulated lender proposals, including principal, rate, tenure, fees, insurance or other charges, net disbursal, repayment schedule, APR/effective annualized cost where calculable, and total repayment/cost.
- Up to three rounds of simulated lender negotiation, subject to available negotiation rules and updated offers being re-audited.
- Supervisor-controlled GO/NO-GO gates, clarification loops, bounded retries, verification and audit logging.
- Approval routing to VP, Finance or Director, Finance based on the final validated amount, with approval/rejection/comments captured in the UI.
- Generation of a proposal pack containing the funding assessment, offer comparison, assumptions, risks, evidence and approval status.

### 4.2 Out of Scope

- Live integration with banks, NBFCs, GST, ERP, accounting, HR or credit-bureau systems.
- Actual loan application submission, sanction, disbursal, acceptance, signing or execution of lender contracts.
- Credit underwriting, credit-score calculation, legal/tax advice, guarantee decisions or a claim that any lender will approve the MSME.
- Use of real employee/customer data in the capstone demonstration; synthetic data and simulated lenders are required.
- Autonomous approval by an AI agent or bypassing finance approval limits.
- A guarantee that the lowest-cost offer is the best commercial option in every circumstance; the system presents a transparent comparison for human review.

---

## 5. Stakeholders and User Roles

| **Role** | **Responsibilities / permissions** |
|---|---|
| Proposal Preparer | Creates a case; completes readiness checks; uploads and corrects source data; reviews the analysis; requests clarification; prepares and submits the proposal for approval. |
| Employee Onboarding Agent | Checks onboarding tasks, required training, policy acknowledgements and task-specific readiness using evidence from simulated systems. |
| Working Capital Advisory Agent | Validates financial inputs, estimates the funding gap, identifies key drivers and produces a funding-needs assessment. |
| LendWise Agent | Audits three lender offers, calculates comparable costs, proposes negotiation moves and creates a comparison. |
| Supervisor / Orchestrator | Routes tasks, enforces prerequisites and GO/NO-GO rules, manages retries and pauses, invokes verification and routes the proposal. |
| Director, Finance | Reviews and approves/rejects proposals below ₹1.5 crore, subject to the boundary clarification noted in this BRD. |
| VP, Finance | Reviews and approves/rejects proposals above ₹1.5 crore. |
| Administrator / Evaluator | Maintains synthetic reference data, policy documents, test cases, configuration and audit/evaluation outputs. |

---

## 6. Target Business Process

| **Step** | **Description** |
|---|---|
| 1. Create case | Proposal preparer signs in to the prototype and creates a case for the MSME, customer order and indicative financing need of ₹2 crore. |
| 2. Check employee readiness | Supervisor invokes the Onboarding Agent. It checks required tasks/training/policies and returns GO, NO-GO or NEEDS_INPUT with evidence. |
| 3. Collect and validate business data | If readiness is GO, the UI collects cash-flow forecasts and supporting data. The Working Capital Agent checks completeness, units, dates, currency, consistency and source evidence. |
| 4. Calculate actual funding requirement | Deterministic code calculates period-by-period cash positions, the timing/size of any funding gap, minimum cash buffer and available funding sources where supplied. The agent explains drivers and assumptions. |
| 5. Gate the funding assessment | If critical data is missing or inconsistent, workflow pauses for clarification. If validated, the agent returns a funding assessment and recommended financing amount with GO. |
| 6. Compare lender offers | LendWise receives the validated financing need and three simulated lender offers. It extracts terms, audits required fields, computes cost metrics in code and compares offers. |
| 7. Negotiate and re-audit | Where enabled, LendWise may request specific improvements for up to three rounds. A concession is not treated as real until a revised offer is received and passes validation and recalculation. |
| 8. Verify proposal | Verification checks calculation outputs, claim-to-evidence traceability, policy citations, offer consistency, unresolved assumptions and safety requirements. |
| 9. Route for approval | Supervisor determines the approval authority from the final validated loan amount and routes the proposal to VP, Finance or Director, Finance. The ₹1.5 crore equality case is held pending clarification. |
| 10. Human decision and close | Approver records approve/reject/return-for-rework and comments. The system records the decision and produces the final proposal pack; it does not accept the loan. |

---

## 7. Functional Requirements

### 7.1 User Interface and Case Management

| **ID** | **Requirement** | **Priority** |
|---|---|---|
| UI-01 | The UI shall allow an authorized preparer to create a case with case ID, MSME details, order context, customer due date, currency and indicative requested amount. | Must |
| UI-02 | The UI shall support upload of structured files and supported PDF/image documents, and show upload/extraction status. | Must |
| UI-03 | The UI shall display each agent's status, decision, evidence, blockers, warnings, timestamp and next workflow action. | Must |
| UI-04 | The UI shall allow the preparer to correct or confirm extracted fields while retaining original source evidence and an audit trail. | Must |
| UI-05 | The UI shall show the calculated funding need separately from the original requested amount. | Must |
| UI-06 | The UI shall show a side-by-side lender comparison and disclose missing or non-comparable terms. | Must |
| UI-07 | The UI shall provide an approval inbox for the designated approver with approve, reject and return-for-rework actions plus comments. | Must |
| UI-08 | The UI shall generate a downloadable proposal pack and decision history. | Must |
| UI-09 | The UI shall support pause/resume without losing case state or creating duplicate tasks/negotiation rounds. | Should |

### 7.2 Employee Onboarding Agent

> The onboarding criteria below are a task-specific qualification overlay built on the Employee Onboarding Buddy project. The exact mandatory training list and role-authorisation rules must be supplied as synthetic policy data for the prototype; the agent must not invent company rules.

| **ID** | **Requirement** | **Acceptance condition** |
|---|---|---|
| ONB-01 | Retrieve the employee profile, assigned role, manager/buddy and onboarding task ledger from simulated systems. | Profile and task status are sourced from simulated records. |
| ONB-02 | Check required onboarding tasks, financial-data handling training, relevant process training and any role-specific prerequisites configured for proposal preparation. | Each prerequisite has a status and evidence/reference. |
| ONB-03 | Answer policy/process questions using retrieved policy excerpts and cite document/section. | Answer is supported by retrieved text; otherwise agent says it cannot verify. |
| ONB-04 | Return GO only when all configured mandatory prerequisites are evidenced as complete and the employee is authorised for the task. | No GO if a mandatory prerequisite is incomplete, unknown or unsupported. |
| ONB-05 | Return NO-GO for failed prerequisites and NEEDS_INPUT for missing or unavailable records; identify the exact blocker and next action. | Supervisor pauses downstream financial workflow. |
| ONB-06 | Never mark an onboarding task complete without evidence from the simulated HR/training system. | Zero false completion on test suite. |
| ONB-07 | Do not request or store Aadhaar, PAN or bank account numbers in chat or onboarding memory. | Sensitive identifiers are rejected/redacted and not persisted. |
| ONB-08 | Persist pending tasks and prior session state for the employee. | Pending-task recall meets the proposed target in Section 12. |

### 7.3 Working Capital Advisory Agent

| **ID** | **Requirement** | **Acceptance condition** |
|---|---|---|
| WC-01 | Collect or extract relevant data: order value and delivery milestones; bill of materials/components; production, labour, testing and logistics costs; opening cash; expected receipts; receivables ageing; payables schedule; inventory; tax/other outflows where supplied; existing limits/available facilities; forecast horizon. | Required fields and source are visible; missing fields are flagged. |
| WC-02 | Validate date ranges, units, currency, duplicate records, totals and cross-document inconsistencies. | Invalid/contradictory data blocks final assessment until resolved or explicitly documented as an assumption. |
| WC-03 | Calculate period-by-period cash position using deterministic code. | Known-answer test cases match expected values within configured rounding tolerance. |
| WC-04 | Estimate the peak funding gap and when it occurs; distinguish cash-flow shortfall from the amount to borrow. | Output includes calculation, timing, assumptions and any minimum cash buffer. |
| WC-05 | Consider available cash, expected collections, supplier credit, existing undrawn facilities and feasible operational mitigations when those data are provided. | No unsupported assumption that all shortfall must be borrowed. |
| WC-06 | Identify potential operational drivers such as slow collections, inventory build-up or supplier payment timing. | Drivers are tied to supplied evidence and labelled as hypotheses where uncertain. |
| WC-07 | Recommend a financing amount and provide a transparent reconciliation from the indicative ₹2 crore request to the calculated requirement. | The output separately reports original request, calculated peak gap, other available funding, recommended amount and rationale. |
| WC-08 | Return GO only when required financial inputs are sufficiently complete and calculations pass validation; otherwise return NEEDS_INPUT or NO-GO. | Supervisor does not invoke LendWise until the required assessment gate passes. |
| WC-09 | Provide a structured output with forecast periods, inputs, formula/version, source references, assumptions, warnings and result. | Output can be reproduced from logged inputs. |

### 7.4 LendWise Agent

> The LendWise requirements adapt the supplied LendWise Team Brief to MSME working-capital offers. Personal-loan-specific rules must not be assumed to apply to business facilities. The prototype should use clearly defined, synthetic business-loan offer records and a configurable rules library.

| **ID** | **Requirement** | **Acceptance condition** |
|---|---|---|
| LW-01 | Accept three lender offers in a defined structured format and/or supported PDF/image formats. | Each offer is associated with lender ID, version and source evidence. |
| LW-02 | Extract facility amount, advertised rate, rate type, tenure, repayment schedule, fees, insurance/other charges, upfront deductions, net disbursal, security/collateral terms where supplied, covenants and validity dates where supplied. | Required fields are validated; missing material terms are flagged. |
| LW-03 | Maintain a verified fact ledger. All financial calculations and numeric facts in comparison/negotiation messages originate from validated data and deterministic code. | No LLM-generated numbers enter the final output without validation. |
| LW-04 | Calculate applicable APR/effective annualized cost where sufficient terms and a suitable calculation method exist, plus net proceeds, scheduled payments, total repayment and total financing cost. | Calculator passes independent test cases; method and assumptions are disclosed. |
| LW-05 | Compare offers against the validated funding requirement, requested availability date, repayment capacity/cash-flow timing and total cost. | Comparison explains trade-offs and flags non-comparable offers. |
| LW-06 | Rank the lowest-cost comparable offer, not merely the lowest advertised rate. | Correct ranking for fully specified test cases; missing information prevents a definitive ranking. |
| LW-07 | Where enabled, select a negotiation move from an approved list and conduct no more than three simulated rounds. | Each move is evidence-based and within configured limits. |
| LW-08 | Treat a concession as effective only after a revised offer is received and re-audited. | No promised or hypothetical concession is included as a verified offer. |
| LW-09 | Block bluffing, invented market rates, false urgency, unsupported claims and acceptance language. | Referee blocks unsafe/unsupported messages; fallback template used if retry fails. |
| LW-10 | Return GO only when offers are sufficiently complete, calculations pass and the comparison is traceable; otherwise return NEEDS_INPUT or NO-GO. | Supervisor does not progress on an unverified comparison. |
| LW-11 | Present the recommendation for human review; never accept or sign a loan on behalf of the MSME. | No acceptance action exists in the UI or tool layer. |

### 7.5 Supervisor / Orchestrator and GO/NO-GO Gates

| **ID** | **Requirement** | **Acceptance condition** |
|---|---|---|
| SUP-01 | Classify the user request and create a workflow plan appropriate to the case. | Uses the required end-to-end sequence for a new proposal. |
| SUP-02 | Invoke the Onboarding Agent first for proposal-preparer qualification. | Working-capital analysis cannot start until readiness GO. |
| SUP-03 | Invoke the Working Capital Agent only after onboarding GO and availability of required financial inputs. | Gate decisions are enforced by code/state machine. |
| SUP-04 | Invoke LendWise only after the funding requirement is validated and approved for comparison. | LendWise receives the calculated amount and relevant constraints. |
| SUP-05 | Require structured decisions from each agent: GO, NO_GO, NEEDS_INPUT or ERROR, with evidence, blockers, warnings and output reference. | Invalid responses fail schema validation and cannot pass the gate. |
| SUP-06 | Evaluate each GO against deterministic mandatory checks; an agent's natural-language assertion alone is insufficient. | Failed deterministic check overrides agent GO. |
| SUP-07 | Handle NEEDS_INPUT by pausing and asking a focused question; resume at the blocked stage after input is supplied. | No unnecessary rerun of completed, unchanged stages. |
| SUP-08 | Handle recoverable errors with bounded retries and idempotent tool calls; escalate persistent or critical errors. | Retry limit and outcome appear in audit log. |
| SUP-09 | Invoke verification before proposal submission and approval routing. | Critical verification failure blocks submission. |
| SUP-10 | Select the approval route from the final validated loan amount and configured threshold. | Route is correct for amounts below/above ₹1.5 crore; equality case is blocked until policy is confirmed. |
| SUP-11 | Persist workflow state and log agent inputs/outputs, decision reasons, tool results and state transitions. | Case can be replayed for evaluation with sensitive data appropriately excluded. |
| SUP-12 | Prevent cross-case access and separate employee memory from customer financial data. | Isolation tests pass. |

### 7.6 Approval Routing and Decision Capture

| **ID** | **Requirement** | **Acceptance condition** |
|---|---|---|
| APR-01 | For a final validated loan amount greater than ₹1.5 crore, route to VP, Finance. | ₹1.50 crore + ₹1 routes to VP Finance. |
| APR-02 | For a final validated loan amount below ₹1.5 crore, route to Director, Finance. | ₹1.50 crore − ₹1 routes to Director Finance. |
| APR-03 | For an amount exactly equal to ₹1.5 crore, pause and request policy clarification until the business owner defines the rule. | No silent default or inferred route. |
| APR-04 | Require approver identity, decision, timestamp and comments/reason where applicable. | Decision is auditable. |
| APR-05 | Support approve, reject and return-for-rework decisions. | Returned cases resume at the relevant workflow stage. |
| APR-06 | Approval does not equal loan acceptance or lender contract execution. | System only records internal proposal approval. |

### 7.7 Verification, Audit and Reporting

| **ID** | **Requirement** | **Acceptance condition** |
|---|---|---|
| VER-01 | Verify material financial claims against the fact ledger, validated calculations and cited source records. | Every material amount/rate/term in report is traceable. |
| VER-02 | Check for missing charges, inconsistent offer versions, unsupported assumptions and unresolved data conflicts. | Critical issues block the report. |
| VER-03 | Check that negotiation messages contain only ledger-backed facts and approved rule citations. | Unsupported claims and acceptance language are blocked. |
| VER-04 | Produce a proposal report with executive summary, business/order context, funding need, cash-flow analysis, assumptions, lender comparison, risks, recommended option and approval routing. | All mandatory sections are present. |
| VER-05 | Maintain an append-only event history for important decisions and changes. | Audit trail identifies actor/agent, event, timestamp, input/output references and decision. |
| VER-06 | Provide a case replay/evaluation mode using synthetic cases. | Evaluators can reproduce results and inspect failed gates. |

---

## 8. Business Rules

| **Rule ID** | **Rule** |
|---|---|
| BR-01 | The indicative request of ₹2 crore is an input, not a pre-approved or fixed final loan amount. |
| BR-02 | The final funding requirement must be derived from validated, period-based cash-flow analysis and available funding sources. |
| BR-03 | The proposal preparer must pass task-specific onboarding readiness before progressing to financial analysis. |
| BR-04 | An onboarding task is complete only when a trusted simulated system provides evidence. |
| BR-05 | Financial calculations are performed by deterministic code; the LLM may explain results but must not originate authoritative numbers. |
| BR-06 | An offer is not considered comparable if material cost or repayment terms required for the chosen comparison method are missing. |
| BR-07 | A revised lender offer replaces an earlier offer only when received, versioned and re-audited. |
| BR-08 | Negotiation is simulated and limited to three rounds; no message may bluff, invent facts or claim an unverified concession. |
| BR-09 | Supervisor must enforce agent gate decisions and mandatory deterministic validations; agent output cannot override a failed gate. |
| BR-10 | Final approval routing uses the final validated recommended loan amount, not the original ₹2 crore request or an unverified offer amount. |
| BR-11 | Amount > ₹1.5 crore routes to VP, Finance; amount < ₹1.5 crore routes to Director, Finance; exactly ₹1.5 crore is unresolved and must be held. |
| BR-12 | A human finance approver decides whether to approve the proposal. The borrower/MSME retains the final choice among lender offers. |
| BR-13 | Customer financial data must be isolated by case and must not be written into general employee onboarding memory. |
| BR-14 | Documents and extracted text are untrusted inputs. Instructions embedded in lender documents are treated as data, not commands. |

---

## 9. Data Requirements and Document Handling

### 9.1 Input Data

| **Data group** | **Example fields** | **Expected source** |
|---|---|---|
| Employee readiness | Employee ID, role, required training, completion evidence, manager/buddy, task status | Simulated HR/training/org-chart records |
| Order context | Customer/order reference, order value, quantity, delivery dates, payment terms, penalties if supplied | Synthetic purchase order / order summary |
| Cash and forecasts | Opening cash, period receipts/payments, minimum cash buffer, forecast horizon | Cash-flow forecast / finance worksheet |
| Receivables | Invoice amount, due date, ageing bucket, expected collection date, customer concentration | Receivables ageing / AR ledger |
| Payables and inventory | Supplier invoice/due date, purchase commitments, stock on hand, work-in-progress, component needs | AP schedule, inventory report, bill of materials |
| Order costs | Component/material costs, labour, production, testing, packaging, logistics and other relevant costs | Order costing / BOM / production plan |
| Existing finance | Cash-credit/OD limits, utilisation, undrawn availability, existing repayments and security if supplied | Synthetic facility statement |
| Lender offers | Principal, rates, tenure, repayment schedule, fees, insurance, net disbursal, collateral/security, covenants | Three simulated offer/KFS-style records |
| Policy and rules | Onboarding requirements, data-handling policy, finance approval matrix, calculation methodology | Curated rules library / RAG corpus |

### 9.2 Data Handling Requirements

- Retain source filename, page/section or cell reference, extraction confidence/validation status and a link between each material fact and its source.
- Do not silently fill missing financial fields. Ask for clarification or label a clearly permitted assumption; do not produce a definitive comparison where the missing field is material.
- Keep employee profile/task data separate from MSME financial records and lender offers.
- Use synthetic data in development and demonstrations. Apply access controls and redact unnecessary personal or account identifiers.
- Treat OCR and vision extraction as provisional until the user or validation rules confirm critical values.

---

## 10. Non-Functional Requirements

| **ID** | **Requirement** |
|---|---|
| NFR-01 | **Reliability:** deterministic calculation functions must be independently unit-tested and reproducible from logged inputs. |
| NFR-02 | **Traceability:** each material report claim must map to a source record, validated fact or calculation output. |
| NFR-03 | **Security:** role-based access and case-level isolation; no secrets committed to source control. |
| NFR-04 | **Privacy:** use synthetic data; avoid collecting unnecessary personal identifiers; keep employee and customer memory separate. |
| NFR-05 | **Safety:** fail closed on critical missing data, failed mandatory checks, unsupported claims or unresolved routing rules. |
| NFR-06 | **Usability:** show plain-language explanations for blockers, required user actions and agent decisions. |
| NFR-07 | **Performance:** prototype should complete the synthetic end-to-end happy path within an agreed demo target; measure latency by stage. |
| NFR-08 | **Maintainability:** agent tools, decision policies, calculation rules and UI should be modular and version-controlled. |
| NFR-09 | **Model constraint:** follow the supplied capstone constraint of a hosted instruct model with 8B parameters or less and no fine-tuning, if this is still the applicable course requirement. |
| NFR-10 | **Observability:** record workflow transitions, tool errors, retries, evaluation results and model/tool versions without logging unnecessary sensitive content. |

---

## 11. Exception Handling

| **Scenario** | **Expected system behaviour** |
|---|---|
| Mandatory onboarding incomplete | Onboarding returns NO-GO; show missing tasks and owner; block financial workflow. |
| Employee/training record unavailable | Return NEEDS_INPUT or ERROR; do not infer qualification. |
| Missing or inconsistent cash-flow data | Pause at Working Capital Agent; list exact fields and conflicts; resume after correction. |
| Calculated funding need differs from ₹2 crore | Display reconciliation and reasons; use validated requirement for offer comparison; do not force the initial amount. |
| Loan offer has unreadable rate or missing fee | Flag source location; ask for corrected document/manual confirmation; no definitive ranking until resolved. |
| Loan calculation fails validation | Block comparison; report failing check and escalate after bounded retry. |
| Lender negotiation refuses or does not respond | Keep last verified offer; do not assume a concession; proceed with available valid offers if comparison remains possible. |
| Prompt injection inside uploaded document | Treat it as untrusted document content; do not follow instructions; log security event. |
| Verification fails | Block submission; route back to the responsible agent for correction or human review. |
| Approval authority boundary is exactly ₹1.5 crore | Pause and request policy clarification; do not route automatically. |
| Approver rejects or returns proposal | Record reason; notify preparer; reopen the relevant stage without losing prior audit history. |

---

## 12. Acceptance Criteria and Evaluation

> The following targets are proposed for the capstone prototype. They should be confirmed and frozen against a labelled test set before final evaluation.

| **Area** | **Measure** | **Proposed target** |
|---|---|---|
| Onboarding | Pending-task recall across prior sessions | ≥90% |
| Onboarding | Correct policy answers with citations | ≥85% |
| Onboarding | Tasks marked complete without evidence | 0 |
| Working capital | Cash-flow and funding-gap calculation accuracy on known-answer tests | 100% |
| LendWise | APR/effective annualized cost accuracy within defined tolerance where calculable | 100% |
| LendWise | Recall of planted material charges/fees in supported offers | ≥95% |
| LendWise | Correct lowest-cost comparable offer ranking | ≥95% |
| Verification | Unsupported material financial claims in frozen safety set | 0 |
| Supervisor | Correct routing across workflow test cases | ≥90% |
| Supervisor | Critical failed mandatory checks that incorrectly pass a gate | 0 |
| Approval | Correct routing below and above ₹1.5 crore | 100% |
| End-to-end | Eligible fully specified cases completed without manual intervention beyond planned review | ≥90% |
| Safety | Prompt-injection tests that change routing, invent a fact or trigger acceptance | 0 |

Test coverage should include happy paths, incomplete inputs, conflicting documents, poor scans, hidden charges, incorrect EMI/rate combinations, lender refusal, prompt injection, access isolation, approval rejection and the ₹1.5 crore boundary case.

---

## 13. Assumptions, Dependencies and Constraints

### 13.1 Assumptions

- The ₹2 crore amount is an indicative initial request for the scenario, not a confirmed final need.
- The MSME has an identifiable customer order and can provide synthetic order-costing and cash-flow information for the demonstration.
- Three simulated lenders provide structured offer records and can return revised offers during negotiation.
- The company has a defined onboarding checklist, required training and role-authorisation policy that can be represented in synthetic records.
- The approval matrix uses the final validated recommended loan amount, subject to confirmation by the business owner.

### 13.2 Dependencies

- Three supplied source documents: Employee Onboarding Buddy project plan, LendWise Team Brief PDF, and the FinBridge AI capstone concept/project plan.
- Synthetic employee profiles, onboarding tasks, policies, manufacturing financial cases, customer order and lender offer documents.
- Agreed cash-flow calculation definitions, loan-cost calculation methodology and rules for non-comparable offers.
- Named business owner to confirm approval routing for exactly ₹1.5 crore and task-specific employee qualification requirements.

### 13.3 Constraints

- Capstone-scale build with simulated systems and no live bank integrations.
- Course constraints in the source briefs indicate a hosted model of 8B parameters or less and no fine-tuning; verify applicability for the combined project.
- The LendWise source brief was designed for personal loans. Its principles—code-owned calculations, fact ledger, audited negotiation, critic and borrower autonomy—are reused, but the business-loan calculation and compliance rules must be separately defined and validated.
- The prototype is not a substitute for finance, treasury, credit, legal or regulatory review.

---

## 14. Risks and Mitigations

| **Risk** | **Impact** | **Mitigation** |
|---|---|---|
| Incorrect financial document extraction | Wrong funding need or lender ranking | Source evidence, validation, confirmation for critical fields, and no definitive ranking on material ambiguity. |
| LLM invents a figure or rule | Misleading proposal | Deterministic calculators, fact ledger, retrieval citations and verification gate. |
| Working capital need overstated | Excess borrowing or unnecessary cost | Use period cash-flow modelling; consider collections, supplier terms, existing facilities and operational mitigations when data exists. |
| Personal-loan methodology incorrectly applied to MSME facilities | Invalid comparison | Define business-facility schemas and calculations; use APR/effective cost only where methodology is appropriate and disclose assumptions. |
| Wrong approver routing | Governance failure | Code-enforced threshold; tests around the boundary; hold exactly ₹1.5 crore pending clarification. |
| Prompt injection in documents | Unsafe tool use or false output | Treat documents as untrusted data; restrict tools; validate every state transition and outgoing claim. |
| Employee memory exposes customer financial data | Privacy breach | Separate storage namespaces and access controls; test cross-case isolation. |
| Negotiated offer not actually confirmed | False savings claim | Version offers and recalculate only from received revised offer records. |
| Scope too broad for capstone time | Incomplete demo | Prioritise structured data, simulated systems and core gates; add OCR/vision fallback after happy path works. |

---

## 15. Implementation Approach and Deliverables

| **Phase** | **Key activities** | **Deliverables / exit gate** |
|---|---|---|
| Phase 1 — Requirements and contracts | Confirm business rules, data schema, GO/NO-GO contract, synthetic cases and approval matrix. | Approved BRD; schemas; frozen acceptance criteria; sample dataset. |
| Phase 2 — Orchestration skeleton | Build UI, case state, Supervisor routing, audit events and mock agents. | End-to-end mock workflow; NO-GO blocks progression. |
| Phase 3 — Onboarding | Implement task ledger, simulated HR/training records, policy RAG and readiness decision. | Evidence-backed readiness gate and tests. |
| Phase 4 — Working capital | Implement financial data intake, validation, period cash-flow model and funding-gap output. | Reproducible calculation results and funding assessment. |
| Phase 5 — LendWise | Implement offer schema, charge audit, calculator, comparison, simulated negotiation and fact ledger. | Three-offer comparison with up to three audited rounds. |
| Phase 6 — Verification and approval | Implement critic, claim audit, approval routing, approval UI and report output. | Verified proposal pack; finance decision captured; no automatic loan acceptance. |
| Phase 7 — Evaluation and demo | Run frozen test suite, negative tests, metrics and demonstration rehearsal. | Evaluation report, known limitations, code and demo recording. |

### 15.1 Recommended Technical Implementation

| **Layer** | **Suggested tools** |
|---|---|
| UI | Streamlit |
| Workflow orchestration | LangGraph or a typed state machine with conditional routing |
| LLM and structured outputs | Hosted instruct model within the course constraints; Pydantic schemas |
| PDF and image intake | PyMuPDF/pdfplumber; OCR such as Tesseract; vision model fallback for difficult scans |
| Calculations | Python Decimal for currency/financial arithmetic; pandas for tabular data; independent unit tests |
| Policy retrieval | FAISS or Chroma with a local embedding model; citations to source documents/sections |
| Persistence | SQLite for prototype case state, tasks, offers, decisions and audit events |
| Testing/observability | pytest, structured logs, frozen JSONL test cases and evaluation metrics |
| Version control | Git; environment variables for secrets; synthetic data only |

### 15.2 Core Deliverables

- Business Requirements Document (this document) and clarified decision log.
- Functional prototype with UI, Supervisor and three specialist agents.
- Synthetic onboarding, manufacturing case and three-lender offer datasets.
- Calculation engine with unit tests and documented assumptions.
- GO/NO-GO workflow and approval routing tests.
- Verification/audit trail and downloadable proposal report.
- Evaluation results, safety test cases, limitations and demo script/recording.

---

## 16. Open Questions / Decisions Required

| **ID** | **Question / decision** | **Why it matters** | **Owner** |
|---|---|---|---|
| Q-01 | Who approves a final loan amount exactly equal to ₹1.5 crore? | The stated rule covers above and below only. | Business owner / Finance |
| Q-02 | Does the threshold apply to the calculated funding need, recommended facility amount, requested amount or lender offer amount? | Determines routing and avoids inconsistent approval. | VP Finance / Director Finance |
| Q-03 | What exact employee training and authorisation requirements qualify a proposal preparer? | Onboarding Agent needs authoritative criteria. | HR / Finance process owner |
| Q-04 | What forecast horizon and minimum cash buffer should the funding model use? | Affects the peak gap and recommended facility amount. | Finance / Treasury |
| Q-05 | Which financing types are included (cash credit, overdraft, working-capital demand loan, term loan, invoice discounting, etc.)? | Cost calculations and comparisons differ by facility type. | Finance / Lending SME |
| Q-06 | What cost metric determines 'lowest cost' for business facilities, and how should collateral/covenants/availability be weighed? | APR may not be comparable or sufficient for every facility. | Finance / Lending SME |
| Q-07 | Are negotiation messages sent only to simulated lenders, and what concessions are permitted? | Defines safe negotiation scope. | Product owner |
| Q-08 | What documents and formats are required for the MVP demo? | Controls OCR and parsing scope. | Project team |
| Q-09 | Should the finance approver approve the proposal only, or also select a preferred lender? | Separates internal proposal approval from borrower/lender acceptance. | Business owner |

---

## Appendix A. Illustrative Case and Outputs

Illustrative case: an electronics manufacturing MSME receives a confirmed order and estimates that ₹2 crore may be needed to buy components, fund production and fulfil delivery milestones. The proposal preparer uploads the order, order-costing/BOM, cash-flow forecast, receivables ageing, payables schedule, inventory and existing facility information.

| **Stage** | **Example output** |
|---|---|
| Onboarding | GO — mandatory task-specific training and authorization evidence found; or NO-GO with missing prerequisite list. |
| Working capital | Calculated peak cash shortfall, timing, available offsets/facilities, assumptions and recommended facility amount; no pre-judgement that it must equal ₹2 crore. |
| LendWise | Three validated offer records, net disbursal, rate and charge breakdown, repayment schedule, total cost, applicable APR/effective cost, negotiation history and ranked comparison. |
| Verification | Claim/evidence audit, calculation checks, unresolved limitations and GO/NO-GO. |
| Approval | Route based on final validated amount: >₹1.5 crore to VP Finance; <₹1.5 crore to Director Finance; exactly ₹1.5 crore held pending decision. |
| Final report | Executive summary, business need, cash-flow evidence, financing options, recommendation, risks, assumptions, approver decision and audit reference. |

---

## Appendix B. Glossary

| **Term** | **Definition** |
|---|---|
| MSME | Micro, Small and Medium Enterprise. |
| Working capital | Funds used to meet operating cash needs such as components, inventory, wages and supplier payments while awaiting collections. |
| Funding gap | The projected shortfall in cash over a defined period after considering expected receipts, payments and available funding sources included in the model. |
| APR / effective annualized cost | An annualized borrowing-cost measure that includes applicable charges when the product terms and methodology support a reliable calculation. |
| KFS | Key Facts Statement; the supplied LendWise brief uses KFS-based offer auditing as its source design. For the business-loan prototype, applicable documentation requirements must be confirmed. |
| Fact ledger | A structured, auditable record of verified facts and calculation outputs used to generate comparisons and messages. |
| GO / NO-GO gate | A controlled workflow decision that determines whether the next dependent step may proceed. |
| Simulated lender | A fictional lender service used for capstone testing; it does not represent a real offer or guarantee of credit. |

---

*FinBridge AI BRD · Version 1.0 · 25 October 2026*
