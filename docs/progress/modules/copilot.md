# Copilot

**Owner:** [Name 6] (TODO: name); plan v3.4: Suresh (retrieval, P4), Tejas (answering, P5)
**Phases:** P0 (dev split), P4 (CP2-R), P5 (CP2-A), P6 (course re-run), P13 (product assistant, ADR 0035)
**Status:** 9e done except CP-01 (regulatory 10/25 live, OPEN); KR-05 recall@5 24/40 (v1.0) OPEN. **P4 code done 2026-11-18** (contextual headers, glossary rewrite, answerability gate, ladder script); Mac run done: frozen recall@5 23 -> 25/40 (headers), dev 13 -> 17/20 (headers + glossary); reranker only scores for the abstain gate (threshold 0.4066); `evaluation/reports/retrieval-ladder-2026-11-18.md`. **P5 code done 2026-11-18**: span-cited answers (cp_answer 2.0.0, unsupported sentences cut) and dual strict/supported scoring in copilot-live; live re-run pending on the Mac. **P13 built 2026-11-18** (ADR 0035): Ask CredAssure on every page; product help as a cited source; CP-07 code routing; CP-10 case status; CP-11 per-case memory with reset; CP-12 Critic-first streaming, fixed follow-ups, feedback

## Open items
- SUP-02 built 21 Nov (P16 16.1): chat classifies data corrections and approval actions in code (`intent.chat_action`), fixed replies, nothing changes from chat; rerun regulatory items on the Mac before K3 (expected unchanged).
- CP-01: strict ≥ 16/25 with supported reported (ADR 0032, adjustable during testing; BRD ≥ 20/25 reported as original) — retrieval-bound (HISTORY "Phase 9e notes", "Phase 10b notes" item 9).
- KR-05 recall@5 target 34/40 (plan v3.4 interim ≥ 30/40) (HISTORY "Current phase").
- Reranker on (ADR 0032, user decision 2026-11-18); report with and without.
- Retrieval dev split (`evaluation/retrieval/dev/`, 20 queries + 8 dev-only unanswerable) drafted; labels `proposed` until a person confirms them (P0 0.3). Whole-document labels fixed to `exact: false` in P4 (exact + empty path matched almost nothing).
- KR-05 interim target 30/40 not met (best 25/40 on v1.0 labels; the labels are pooling-biased); P5 measures the copilot end to end with the new settings, including false abstains on the 25 regulatory items.
- P5 live re-run (make copilot-live on the Mac): coverage, strict/supported, safety 8/8/3; then review the J1 human sample.
- P13: live G4 run shows the effect of code routing on the 25 regulatory items (11 now code-routed to search_regulations); a held-out routing set (the 40 in `evaluation/copilot/dev/` are dev only).
- P13: help pages are a cited source; review `docs/help/ask-credassure.md` and `docs/help/ai-safety.md` like code.
