# ADR 0021: Calculation conventions shared by gold and engines

Status: Accepted · 2026-11-05 · Phase 3 (gold), binds Phase 4 (engines) · WC-03..06, LW-02..14, BR-09

## Context
The independent gold (`evaluation/src/credassure/evaluation/gold/`) and the Phase 4 engines must agree on conventions
the BRD leaves open. Otherwise a correct engine fails the frozen test set. The money-auditor's Phase 3 review listed
them, and this ADR settles them. Gold and engines are still implemented independently; only these rules are shared.

## Decision

**Funding (WC)**
- **Cash table:** cumulative cash = opening cash + confirmed receipts + receivables in their **expected** week −
  costs − payables in their **due** week. Rows after week 26 are ignored. Inventory is information only.
- **Mitigations:** reduce the need only if they have an `evidence_ref` and arrive **on or before the peak week**.
  They are never cash inflows (WC-05).
- **Need:** max(0, peak + buffer − undrawn limits − qualifying mitigations), rounded **up** to ₹1 lakh.
  - The bridge from the ₹2 crore request sums exactly to it: request, peak − request, buffer, −undrawn,
    −mitigations, floor at zero, lakh round-up.
  - `peak_week` is the week of the lowest cumulative cash even when there is no shortfall.
  - `shortfall_weeks` counts the weeks below zero.
- **NEEDS_INPUT:** a missing opening-position field, order receipts that don't sum to the order value, or a
  duplicate invoice or bill ID.

**Offers (LW)**
- **Pricing:** borrower cash flows from disbursal. Month 0 is the principal less:
  - upfront fees (+ GST where flagged);
  - insurance not financed;
  - year-1 annual charges;
  - the year-1 CGTMSE fee on the guaranteed amount (+ GST where flagged).

  Payment k falls on disbursal + k calendar months (day capped at 28). An offer whose `first_repayment_date` is not
  disbursal + (moratorium + 1) months is non-comparable (`LW_SCHEDULE_DATE_MISMATCH`). Interest is paid monthly
  during the moratorium. Annual charges fall at months 0, 12, … below the tenure, and CGTMSE is charged on the
  outstanding balance at each anniversary.
- **APR:** monthly IRR × 12 (nominal, ADR 0012).
- **GST:** on fees and charges only, never on interest.
- **Hidden charges:** charges in the offer's schedule of charges (`<kfs_doc_id>-SCH`) that are missing from the offer
  record are flagged (LW-04) **and priced into the APR and total cost**.
- **Comparable:** every material term present (principal, rate, tenure, fee schedule, repayment, disbursal date), the
  stated instalment within ₹1, and the schedule date consistent.
- **Affordable (LW-09):** for every week, cash + undrawn limits + mitigations + amount received (from the disbursal
  week) − payments so far ≥ minimum buffer.
- **Late or short (LW-10):** the disbursal week is after the peak week, or the **principal** is below the need.
- **Ranking:** eligible offers (comparable, affordable, not late or short) by APR, then total cost, then disbursal
  date. Gate GO needs at least two.
- **No need:** when the need is ₹0, the lender comparison is `NOT_REQUIRED`, with no ranking and no loan.
- **Warnings:** `LW_CGTMSE_INELIGIBLE` (guarantee on a medium enterprise) and `LW_BENCHMARK_NOT_EXTERNAL` (MSE
  floating rate not on EBLR) are **warnings**. They do not make an offer non-comparable.
- **Not priced yet:** financed insurance, and CGTMSE bases other than "year 1 guaranteed, then outstanding". Gold
  raises an error on them until a convention is agreed.

**Negotiation (LW-12/13, BR-09/10)**
- **Target:** the comparable offer with the highest processing fee. It cites the lowest processing fee among the
  other comparable offers. With fewer than two comparable offers there is no message.
- **Concession:** counts only when the received revised version re-audits as comparable **and** its fee is lower.

## Consequences
The Phase 4 engines implement these rules from this ADR, not from the gold code. Known-answer tests compare the two.
Any change needs a new ADR and, after G1, a v2 test set.
