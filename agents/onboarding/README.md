# onboarding

Owner: Tejas. Requirements: ONB-01..06, BR-03, BR-04. Gate 1, preparer readiness (design-detail §2.4.2).

| | |
|---|---|
| Inputs | The case preparer's HR profile. `emp_id` comes from the login binding (`users.emp_id`), never from chat (ONB-01) |
| Tools | `get_hr_profile`, `evaluate_onboarding_rules` (read-only; hr.db opened `mode=ro`, ONB-05) |
| Data access | `hr_profile` and ledger keys `onb.*` only; case financials are refused by the tool layer (scope #24) |
| Gate (code) | all rules PASS → GO; any FAIL → NO_GO; otherwise an UNKNOWN (missing record) → NEEDS_INPUT with one question |
| Model | `onb_explain` words the failed rules and next actions from the rule table only. A reply that does not name every failed rule id is replaced by the template (ONB-04); no model call on GO |
| Writes | `onb.rule.<role|AML-201|DPDP-101|FIN-101|policy_ack>` = PASS/FAIL/UNKNOWN, `onb.gate` |
| Re-check | The Supervisor recomputes readiness from hr.db on every GO; a disagreeing fact → NO_GO + `GATE_OVERRIDE` (SUP-05) |
| Eval | 10 onboarding items (T026–T035), E5 |

Stage runs go through `SupervisorPort.start_run` on the gateway. This agent calls no other agent and has no path that accepts a lender offer.
