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
  *Amended 2026-11-21 (LW-01, BR-06):* the engine still prices neither, but an offer that carries one no longer
  stops the comparison. `offer_audit.invalid_terms()` makes it non-comparable with the flag
  `LW_OFFER_INVALID:<term>` before any calculation, as it does for a value no loan has (principal or rate ≤ 0, a
  rate above 100% a year, tenure outside 1–360 months, no repayment month, a negative fee or premium). The offer
  is never priced or ranked, the offers view names the terms (`invalid_terms`), and the other offers are compared.
  No frozen offer has such a term, so gold and every frozen result are unchanged.

**Phase 9c-a additions**
- **GST split:** the GST on each offer is reported as CGST + SGST in equal halves (paise, half-up), treating the
  supply as intra-state for the home state IN-MH (ADR 0019, R-GST-01). An inter-state lender would charge IGST at
  the same total, so the APR is unaffected.
- **GST on schedule rows:** a charge is taxed unless its row states it is exempt (LW-06); every frozen row says
  "+ GST", so gold is unchanged.
- **Unreadable rows:** an undeclared schedule row whose amount code cannot read is flagged `LW_HIDDEN_CHARGE` and
  makes the offer non-comparable (fail closed), never dropped.
- **Model extraction:** the model's charge list is a cross-check recorded in `lw.kfs.<doc>.extraction`; prices
  always come from the code parse of the schedule, so the model's reading cannot change an APR.
- **Ranking ties:** APRs equal at 0.01 pp go to total cost, as gold ranks on the displayed APR.

**Negotiation (LW-12/13, BR-09/10)**
- **Target:** the comparable offer with the highest processing fee **in rupees** (fraction x principal for a
  percentage fee; engine and gold both, pinned 2026-11-16). It cites the lowest such fee among the other comparable
  offers. The message states each fee by its basis (percentage of the loan amount, or rupees).
- **Once per case:** a request that was sent locks the round (`lw.negotiation.status = sent`, under the case run
  lock); "no competitor" and a message blocked by verification can be retried. The revision is recorded as
  `lw.negotiation.revised.*` facts; it changes the ranking only once the preparer uploads it and re-runs the stage. With fewer than two comparable offers there is no message.
- **Concession:** counts only when the received revised version re-audits as comparable **and** its fee is lower.

## Consequences
The Phase 4 engines implement these rules from this ADR, not from the gold code. Known-answer tests compare the two.
Any change needs a new ADR and, after G1, a v2 test set.
