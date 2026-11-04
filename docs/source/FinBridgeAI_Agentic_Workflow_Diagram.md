# FinBridge AI — Agentic Workflow Diagram

> Loan proposal workflow for an Electronics Manufacturing MSME

---

## Workflow Overview

```
Employee logs in and initiates loan proposal for a customer (Electronics Manufacturing MSME)
         │
         ▼
┌─────────────────────────────────┐
│   2. Employee Onboarding Agent  │
│  • Verify employee identity     │
│    and role                     │
│  • Check mandatory training,    │
│    certifications and approvals │
│  • Confirm eligibility to       │
│    prepare loan proposal        │
└────────────┬────────────────────┘
             │
      Qualified to prepare proposal?
             │
      ┌──────┴──────┐
     YES            NO
    (Go)          (No-Go)
      │              │
      │    ┌─────────▼──────────────────────┐
      │    │ Provide guidance / Complete     │
      │    │ pending onboarding and training │◄──┐
      │    └────────────────────────────────┘   │ (loop back)
      │
      ▼
┌──────────────────────────────────────────┐
│   3. Working Capital Advisory Agent      │
│  • Analyze order details                 │
│  • Evaluate cash flows, receivables,     │
│    payables, inventory and financial data│
│  • Calculate actual funding gap and      │
│    recommend loan amount (e.g., ₹2 crore)│
└──────────────────┬───────────────────────┘
                   │
          Funding analysis approved?
                   │
           ┌───────┴───────┐
          YES              NO
          (Go)           (No-Go)
           │                │
           │   ┌────────────▼──────────────────────────┐
           │   │ Request additional/updated financial   │◄──┐
           │   │ information                            │   │ (loop back)
           │   └────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────┐
│   4. LendWise Agent                      │
│  • Collect loan proposals from 3 lenders │
│  • Calculate true cost (APR, fees,       │
│    insurance, etc.)                      │
│  • Optionally negotiate (up to 3 rounds) │
│  • Compare offers and recommend lowest   │
│    cost option                           │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│   5. Final Loan Proposal                 │
│  • Consolidate analysis and recommended  │
│    lender                                │
│  • Include loan amount, terms, cost      │
│    comparison and rationale              │
│  • Attach key documents and evidence     │
│  • Generate proposal report              │
└──────────────────┬───────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│   6. Approval Routing                    │
│                                          │
│      Loan amount > ₹1.5 crore?           │
│                                          │
│   YES ──► Submit to VP, Finance          │
│           (for approval)                 │
│                  │                       │
│   NO  ──► Submit to Director, Finance    │
│           (for approval)                 │
└──────────────────┬───────────────────────┘
                   │
              Approved?
                   │
           ┌───────┴──────────┐
          YES                 NO
           │                  │
           ▼          ┌───────▼──────────────────────┐
 ┌─────────────────┐  │ Provide feedback /           │
 │  7. Complete    │  │ Revise and resubmit          │──► (back to Step 4)
 │                 │  └──────────────────────────────┘
 │ Approved loan   │
 │ proposal ready  │
 │ for submission  │
 │ to lender       │
 └─────────────────┘
```

---

## Agent Descriptions

### 1. Start
Employee logs in and initiates a loan proposal for a customer (Electronics Manufacturing MSME).

---

### 2. Employee Onboarding Agent
**Responsibilities:**
- Verify employee identity and role
- Check mandatory training, certifications and approvals
- Confirm eligibility to prepare loan proposal

**Gate:** Qualified to prepare proposal?
- **Go** → proceed to Working Capital Advisory Agent
- **No-Go** → provide guidance / complete pending onboarding and training (loop back)

---

### 3. Working Capital Advisory Agent
**Responsibilities:**
- Analyze order details
- Evaluate cash flows, receivables, payables, inventory and financial data
- Calculate actual funding gap and recommend loan amount (e.g., ₹2 crore)

**Gate:** Funding analysis approved?
- **Go** → proceed to LendWise Agent
- **No-Go** → request additional/updated financial information (loop back)

---

### 4. LendWise Agent
**Responsibilities:**
- Collect loan proposals from 3 lenders
- Calculate true cost (APR, fees, insurance, etc.)
- Optionally negotiate (up to 3 rounds)
- Compare offers and recommend lowest cost option

---

### 5. Final Loan Proposal
**Consolidates:**
- Analysis and recommended lender
- Loan amount, terms, cost comparison and rationale
- Key documents and evidence
- Proposal report

---

### 6. Approval Routing
**Business Rule:**
- Loan amount **> ₹1.5 crore** → Submit to **VP, Finance** (for approval)
- Loan amount **≤ ₹1.5 crore** → Submit to **Director, Finance** (for approval)

**Gate:** Approved?
- **Yes** → Complete (Step 7)
- **No** → Provide feedback / Revise and resubmit (loop back to Step 4)

---

### 7. Complete
Approved loan proposal ready for submission to lender.

---

## Supervisor / Orchestrator Agent

> Runs throughout the entire flow

**Responsibilities:**

| Function | Description |
|---|---|
| Context understanding | Understands user request and context |
| Agent invocation | Invokes the right agent at each step |
| Gate management | Receives GO / NO-GO from each agent |
| Rule enforcement | Enforces business rules and approval routing |
| Progress tracking | Tracks progress and maintains audit log |
| User communication | Provides unified status and explanations in the UI |

---

## GO / NO-GO Gate Summary

| Gate | Condition | GO outcome | NO-GO outcome |
|---|---|---|---|
| Employee Onboarding | All mandatory training, certifications and authorisations complete | Proceed to Working Capital analysis | Provide guidance; complete pending onboarding |
| Funding Analysis | Financial data validated; funding gap calculated | Proceed to LendWise | Request additional/updated financial information |
| Final Approval | Approver (VP Finance or Director Finance) approves | Proposal ready for lender submission | Provide feedback; revise and resubmit |

---

*FinBridge AI · Agentic Workflow Diagram · 25 October 2026*
