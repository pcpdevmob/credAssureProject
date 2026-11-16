# ADR 0023 — Ledger facts and audit events are the record for offers, evaluations and negotiation

Status: Accepted · Date: 2026-11-16 · Records a Phase 9c deviation from design-detail §4

## Context
design-detail §4 lists `offers`, `offer_evaluations` and `negotiation_messages` tables in case.db. Phase 9c built LendWise
without writing them: offers and KFS documents arrive as versioned `case_files` uploads, and every computed result is a
ledger fact.

## Decision
One source of truth:
- **Offer inputs:** `case_files` rows (kind `offer` / `kfs`, newest version wins, old kept, sha256), read only through the
  `load_offers` tool (ADR 0009).
- **Evaluations:** ledger facts `lw.<offer_id>.v<n>.{amount_received,total_repayment,total_cost,apr,flags,rank,comparable,…}`
  with source, engine version and input hash (lineage, scope #33).
- **Negotiation:** ledger facts `lw.negotiation.*` (target, fees, template, rendered message, status, revised figures,
  `concession_counts`) plus audit events for the send, the reply scan and the re-audit.

The three tables are not written. Phase 10 drops them in an Alembic migration (upgrade and downgrade tested) together with
any model classes and reads that refer to them.

## Consequences
- Reports, the offers view and the approval inbox read the ledger only; nothing can disagree with a second copy.
- A table-shaped view (e.g. for the evaluator) is a query over facts, not a store.
- design-detail §4 is superseded on these three tables by this ADR.
