# lendwise

Owner: Pritish. Requirements: LW-01..11, LW-14 (9c-a); LW-12/13 negotiation arrives in 9c-b.

Gate 3 lender comparison. Never accepts, signs or submits an offer (BR-13).

- **Inputs:** the case's uploaded offers (`kind=offer`, JSON) and KFS schedules of charges (`kind=kfs`,
  Markdown), plus the funding position recomputed from the case files. Reads `wc.recommended_amount`
  (read-only) and stops if it no longer matches.
- **Tools:** `load_offers`, `audit_offer`, `price_offer`, `check_affordability`, `rank_offers` (engines only).
- **Model:** `lw_kfs_extract` (one call per offer, in parallel; spans checked verbatim; kept only when it equals
  the code parse, else the code parse stands; never changes a price) and `lw_explain` (slot names only).
- **Writes:** `lw.<offer>.v<n>.{apr,amount_received,total_repayment,total_cost,gst,cgst,sgst,flags,
  comparable,affordable,eligible,lowest_cash,rank}`, `lw.ranking`, `lw.gate`, `lw.kfs.<doc>.extraction`,
  `lw.reference_rate.<id>` (cited `R-RATE-02-*`).
- **Gate:** GO with at least two comparable, affordable, on-time offers, or `NOT_REQUIRED` when the need is ₹0;
  else NO_GO with `LW_FEWER_THAN_TWO_ELIGIBLE`. The Supervisor recomputes every `lw.*` fact (SUP-05).
- **API:** `GET /v1/agents/lendwise/cases/{id}/offers` (same view as `/v1/cases/{id}/offers`).
