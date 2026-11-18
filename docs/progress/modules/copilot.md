# Copilot

**Owner:** [Name 6] (TODO: name); plan v3.4: Suresh (retrieval, P4), Tejas (answering, P5)
**Phases:** P0 (dev split), P4 (CP2-R), P5 (CP2-A), P6 (course re-run)
**Status:** 9e done except CP-01 (regulatory 10/25 live, OPEN); KR-05 recall@5 24/40 (v1.0) OPEN. **P4 code done 2026-11-18** (contextual headers, glossary rewrite, answerability gate, ladder script); the Mac run (re-ingest, rungs 0–3, dev curve) is pending: `docs/plan/P4-mac-runbook.md`

## Open items
- CP-01: strict ≥ 16/25 with supported reported (ADR 0032, adjustable during testing; BRD ≥ 20/25 reported as original) — retrieval-bound (HISTORY "Phase 9e notes", "Phase 10b notes" item 9).
- KR-05 recall@5 target 34/40 (plan v3.4 interim ≥ 30/40) (HISTORY "Current phase").
- Reranker on (ADR 0032, user decision 2026-11-18); report with and without.
- Retrieval dev split (`evaluation/retrieval/dev/`, 20 queries + 8 dev-only unanswerable) drafted; labels `proposed` until a person confirms them (P0 0.3). Whole-document labels fixed to `exact: false` in P4 (exact + empty path matched almost nothing).
- P4 Mac run: re-ingest with `RETRIEVAL_CONTEXT_HEADERS=true`, ladder rungs 0–3, threshold from the dev curve, then set the chosen values in the env templates.
