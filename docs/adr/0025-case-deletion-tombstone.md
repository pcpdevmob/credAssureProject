# ADR 0025 — Case deletion: content removed, append-only record kept as a tombstone

Status: Accepted · Date: 2026-11-17 · Phase 10 · Scope #39 · Requirements OBJ-08, APR-04, BR-14, NFR-07

## Context
Scope #39 asks for `DELETE /v1/cases/{id}` with an audit tombstone. `ledger_facts`, `approvals` and `audit_log` are
append-only: SQLite triggers refuse UPDATE and DELETE (OBJ-08, APR-04), and `audit_log` is hash-chained. The Phase 5
security review said: write an ADR first, choose a tombstone or an audited migration-only purge, and never drop the
triggers ad hoc. `scripts/purge_cases.py` (test-data cleanup, used by `make demo-reset`) is the only path that drops
triggers. It does so inside one transaction, and it stays an operator tool.

## Decision
`DELETE /v1/cases/{id}?expected_version=n` (evaluator only, under the case run lock) runs one transaction in
`packages/ledger` (`writes.delete_case`). It:

1. **Removes the case content** from tables that are not append-only: `case_files` (uploaded payloads), `chat_messages`,
   `stage_runs`, `jobs`, `negotiation_messages`, `offer_evaluations`, `offers`, and the LangGraph checkpoint rows for
   the case's thread.
2. **Keeps the record**: `ledger_facts`, `approvals` and `audit_log`. No trigger is dropped and no audit row changes,
   so the hash chain verifies after a delete.
3. **Turns the `cases` row into a tombstone**: `status = DELETED`, `msme_name` and `order_ref` replaced by
   `[deleted]`, `current_stage` cleared. It is an optimistic-concurrency update (`row_version`).
4. **Appends `CASE_DELETED`** with the actor, the case version and the row counts removed, then re-verifies the
   tenant's chain before commit (fail closed).

A tombstoned case is invisible: every case read returns 404, lists and inboxes skip it, and it cannot be run, uploaded
to, chatted about or decided. The one exception is an evaluator reading `GET /v1/cases/{id}/audit`, which shows the
tombstone and `chain_ok`. The case ID is never reused, because IDs are `max(id)+1` and the tombstone row stays.

## Consequences
- What remains after a delete is the minimum record: code-computed figures, PII-redacted narratives, approvals with
  redacted comments, and audit events. All data is synthetic (BRD §10). With real personal data this would need a
  crypto-shredding design instead, because audit payloads cannot be edited.
- `scripts/purge_cases.py` still purges tombstones, so `make demo-reset` keeps stable case IDs.
- Rejected: dropping the triggers for an API delete. It would break OBJ-08 and the "no edit, even by the app" rule.
