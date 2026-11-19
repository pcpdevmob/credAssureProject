# ADR 0037 — Three negotiation rounds by default, re-ranking after every counted concession

Status: Accepted (owner decision 2026-11-19, Pritish: "full app, not a demo: 3 rounds by default and re-rank the offers") ·
Date: 2026-11-19 · Reinstates BRD LW-15 (cut by ADR 0032 §7) · Amends design-detail §2.4.7 step 6 · BRD LW-11, LW-12,
LW-13, BR-09, BR-10, BR-15 · Data: S05 v2 (`data/frozen/v2/lender_scripts`)

## Context
LendWise ran one fee-waiver round with one lender (LW-12). A revised offer was re-audited and re-priced on its own,
but the ranking, the per-offer ranks and the gate were never recomputed: the approver saw the warning
`negotiation_in_progress` and the old order. In the reference run (`var/eval/20261119T091531`) case 06's counted
waiver brought OF-06-A from 16.60% to 12.36% APR, below the top-ranked OF-06-B (13.80%), so the recommendation shown
was the dearer offer. The owner decided the product runs as a full app, not a demo, with three rounds by default.

## Decision
1. **Up to three rounds per case, one per call** of `POST /v1/agents/lendwise/cases/{id}/negotiate` (BRD §6: rounds
   are separate invocations; SUP-07 caps each one). Moves run in a fixed order, each at most once:
   `fee_waiver_v1` → `rate_match_v1` → `tenor_change_v1` (`engines.negotiation.MOVES`). A move with no target is
   skipped without using a round. After the third sent round, or when no move is left, `lw.negotiation.complete` is
   true and the next call answers 409.
2. **Code chooses every move and every cited figure** (pure, `engines.negotiation`):
   - Fee waiver: unchanged (highest processing fee in ₹ among comparable offers; cite the lowest other one).
   - Rate match: the best-ranked fixed-rate eligible offer whose annual rate is above the lowest annual rate of the
     other eligible offers; cite that rate. Floating rates are never targets (they reset). Fewer than two eligible
     offers: no move.
   - Tenor change: the cheapest comparable offer flagged `LW_NOT_AFFORDABLE` whose first repayment falls in or before
     the peak-shortfall week; ask for the fewest extra moratorium months (at most 6) that move the first repayment
     after that week, tenure extended by the same months so the instalment is unchanged. No move otherwise (a longer
     moratorium does not fix a late disbursal or a short principal).
   Each message is a fixed template filled from ledger facts only, checked by `verify_claims` (figures, banned
   wording) before it is sent. No model writes any part of it.
3. **Re-audit, then re-rank (LW-13 → LW-11).** The revised version goes through the same audit, pricing and
   affordability tools together with the other offers in one comparison. When the concession counts (re-audits as
   comparable and is better on the term asked about), the revision is stored (`<prefix>revised.offer`,
   `<prefix>revised.schedule`) and every comparison fact is rewritten: `lw.ranking`, `lw.gate`, per-offer facts at
   the new version. `load_offers` merges stored counted revisions into the uploads, so the stage re-check, a re-run
   and the preview all see the same offers. The report becomes stale and must be regenerated before approval
   (ADR 0003 §3). `negotiation_in_progress` now shows only if a counted concession is newer than the ranking.
4. **Round 1 is unchanged.** The fee waiver writes the same keys (`lw.negotiation.*`), message and figures as before;
   the rate match and tenor change write under `lw.negotiation.rate_match.` and `lw.negotiation.tenor_change.`, each
   with the `round` it ran in. Verified on all 15 frozen cases against the pre-ADR code: the 17 round-1 facts are
   identical. The frozen harness calls negotiate once per item, so the 100 items see round 1 only.
5. **Lender replies for rounds 2-3 come from v2 scripts.** `data/frozen/v1/lender_scripts` answers only the fee
   waiver and stays untouched. `data/frozen/v2/lender_scripts` (generator `credassure.datagen.lender_scripts_v2`)
   copies each v1 fee-waiver reply and adds `rate_match_v1` (`rate_gap_closed`: 1, 0.5 or 0) and `tenor_change_v1`
   (`max_extra_months`: 6, 2 or 0), with planted injection lines for L05 and L09. `LENDER_SCRIPTS_DIR` defaults to v2;
   a v1 directory still runs round 1 and answers later rounds with no revision. The simulator restates the instalment
   after a rate change; the audit checks it independently (LW-03).
6. Unchanged: lender reply text is display-only data (BR-15); no path accepts, signs or submits an offer (BR-13).

## Consequences
- The approver always sees the order with every counted concession in it; case 06 now recommends OF-06-A.
- E7 (negotiation) items keep their gold; T082 (case 03) keeps its order B, C, A after re-ranking (OF-03-A revised
  15.16% stays above OF-03-C 15.03%). Rounds 2-3 are not in the frozen 100 items; they are covered by unit and API
  tests and reported separately.
- In the frozen cases the tenor change raises the lowest cash position but does not restore affordability (the
  moratorium interest still dips below the buffer at the low point); the report says so.
- Limitations: one request per round to one lender; the fee-waiver target is the highest-fee offer, not necessarily
  the one whose concession would change the decision; no counter-offers.
- Data v2 is provisional until a teammate who did not write the replies reviews them (human-review).
