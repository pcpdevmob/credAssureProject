# Gold hand-check (BRD §10: ten gold answers recomputed by hand, independently of the code)

Status: **form ready, not started** (prepared 2026-11-15 for G1). G1 needs all ten rows signed by both named
checkers. Neither checker may own the agent the row tests.

Work from the files in `data/frozen/v1/cases/<case_id>/` and `data/frozen/v1/offers/<case_id>/` in a spreadsheet or on
paper, without running the code. **Do not look at the gold column until your own value is written down**; fold or
hide it if you print this page. Checker 1 and checker 2 work separately and do not compare values before both
are filled in.

**Rules** (the same as `evaluation/gold`):
- Cumulative cash = opening cash + confirmed receipts + receivables in their **expected** week − costs − payables in
  their due week.
- Need = max(0, peak shortfall + buffer − undrawn limits − mitigations), rounded **up** to ₹1 lakh.
- APR = monthly IRR × 12 on: (principal − upfront fees × 1.18 − insurance − year-1 CGTMSE fee) at month 0, then
  interest-only months, then the EMI, plus any charges. GST is applied to fees, never to interest.
- Charges for the APR come from **two** files: the offer (`offers/<case>/<offer>.v1.json`) and its schedule of
  charges (`kfs/<kfs_doc_id>-SCH.md`). A charge listed in the schedule but missing from the offer is priced like
  any other fee (ADR 0021). Row 6 has one.
- Annual charges are paid at month 0 and again at each anniversary before the loan ends (months 12, 24, …). The
  CGTMSE fee is charged on the full loan at month 0 and on the amount still owed at each anniversary, with GST
  only if the offer says `gst_applicable: true`. Row 7 (18 months) has a second fee at month 12.
- Match = both checkers equal the gold value to ₹1 (amounts), 0.01 percentage points (APR), or exactly (routes,
  gates, rule names). A mismatch is not fixed here: write it under "Discrepancies" and tell the eval owner.

## Checkers

| Checker | Areas | Rows |
|---|---|---|
| Tejas | cash flow, offers | 1–4 (checker 1), 5–8 (checker 1) |
| Suresh | offers, routing | 5–8 (checker 2), 9 (checker 1) |
| Abhishek | any | 10 (checker 1) |
| Pritish | cash flow, routing | 1–4 (checker 2), 9 (checker 2), 10 (checker 2) |

Pritish owns LendWise, so the offer rows (5–8) go to Tejas and Suresh.

## Rows

| # | Item | What to recompute | Gold value | Checker 1 | C1 value | C1 date | Checker 2 | C2 value | C2 date | Match? |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | CA-2026-0001 cash flow | peak shortfall, peak week, need | ₹1,62,00,000 · week 9 · ₹1,42,00,000 | Tejas | | | Pritish | | | |
| 2 | CA-2026-0010 cash flow | need (boundary) | ₹1,50,00,000 | Tejas | | | Pritish | | | |
| 3 | CA-2026-0015 cash flow | need | ₹0 | Tejas | | | Pritish | | | |
| 4 | CA-2026-0011 cash flow | need | ₹62,00,000 | Tejas | | | Pritish | | | |
| 5 | OF-01-B (case 1) | APR | 13.00% | Tejas | | | Suresh | | | |
| 6 | OF-01-A (case 1) | APR with fees, GST and insurance | 17.56% | Tejas | | | Suresh | | | |
| 7 | OF-02-B (case 2, CGTMSE) | APR with the guarantee fee | 14.89% | Tejas | | | Suresh | | | |
| 8 | OF-04-A (case 4) | stated vs recomputed instalment | mismatch > ₹1 | Tejas | | | Suresh | | | |
| 9 | Routing | ₹1,49,99,999 / ₹1,50,00,000 (hold) / ₹1,50,00,001 | director / HELD / vp | Suresh | | | Pritish | | | |
| 10 | E020 onboarding | failed rules | FIN-101 and policy_ack → NO_GO | Abhishek | | | Pritish | | | |

## Discrepancies

| # | Checker | Their value | Gold value | Working (short) | Resolution (eval owner) |
|---|---|---|---|---|---|
| | | | | | |

## Sign-off

By signing, each checker confirms they worked without running the code or reading `evaluation/gold/`, and that
every value in their column is their own.

| Checker | Rows | All match? | Signature / initials | Date |
|---|---|---|---|---|
| Tejas | 1–8 | | | |
| Suresh | 5–9 | | | |
| Abhishek | 10 | | | |
| Pritish | 1–4, 9, 10 | | | |
