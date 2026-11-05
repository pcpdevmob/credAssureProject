# Gold hand-check (BRD §10: ten gold answers recomputed by hand, independently of the code)

Status: **not started**. G1 needs all ten rows signed by two people. Neither may be the owner of the agent the item tests.

Work from the files in `data/frozen/v1/cases/<case_id>/` and `data/frozen/v1/offers/<case_id>/` in a spreadsheet or on
paper, without running the code.

**Rules** (the same as `evaluation/gold`):
- Cumulative cash = opening cash + confirmed receipts + receivables in their **expected** week − costs − payables in
  their due week.
- Need = max(0, peak shortfall + buffer − undrawn limits − mitigations), rounded **up** to ₹1 lakh.
- APR = monthly IRR × 12 on: (principal − upfront fees × 1.18 − insurance − year-1 CGTMSE fee) at month 0, then
  interest-only months, then the EMI, plus any charges. GST is applied to fees, never to interest.

| # | Item | What to recompute | Gold value | Checker 1 | Checker 2 | Match? |
|---|---|---|---|---|---|---|
| 1 | CA-2026-0001 cash flow | peak shortfall, peak week, need | ₹1,62,00,000 · week 9 · ₹1,42,00,000 | | | |
| 2 | CA-2026-0010 cash flow | need (boundary) | ₹1,50,00,000 | | | |
| 3 | CA-2026-0015 cash flow | need | ₹0 | | | |
| 4 | CA-2026-0011 cash flow | need | ₹62,00,000 | | | |
| 5 | OF-01-B (case 1) | APR | 13.00% | | | |
| 6 | OF-01-A (case 1) | APR with fees, GST and insurance | 17.56% | | | |
| 7 | OF-02-B (case 2, CGTMSE) | APR with the guarantee fee | 14.89% | | | |
| 8 | OF-04-A (case 4) | stated vs recomputed instalment | mismatch > ₹1 | | | |
| 9 | Routing | ₹1,49,99,999 / ₹1,50,00,000 (hold) / ₹1,50,00,001 | director / HELD / vp | | | |
| 10 | E020 onboarding | failed rules | FIN-101 and policy_ack → NO_GO | | | |
