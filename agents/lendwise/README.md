# lendwise

Owner: Pritish. Requirements: LW-01..14.

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
- **Negotiation (LW-12/13):** `POST /v1/agents/lendwise/cases/{id}/negotiate`, one round per case, a separate
  invocation through the Supervisor. Target and competing fee from `engines.negotiation.plan`, written as
  `lw.negotiation.*` facts; `fee_waiver_v1` (code template) filled from those facts; `verify_claims` (interim
  Critic: every figure in the ledger, no acceptance/urgency wording) before `lender_send_template`; the reply is
  scanned (`lw.negotiation.reply_flags`) and never reused as text; a revision is re-audited and re-priced
  before `lw.negotiation.concession_counts` and `lw.negotiation.revised.*` are written.
- **API:** `GET /v1/agents/lendwise/cases/{id}/offers` (same view as `/v1/cases/{id}/offers`).
