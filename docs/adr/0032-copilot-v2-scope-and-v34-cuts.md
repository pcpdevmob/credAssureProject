# ADR 0032 — Copilot v2 reduced scope, dual scoring, reranker on, and the plan v3.4 cuts

Status: Accepted (user decisions 2026-11-18: reranker yes; copilot target set by Claude, adjustable during testing) · Date: 2026-11-18 · Plan v3.4 §7, §9 · Scope #60–#64 · Amends ADR 0013 (reranker default), BRD §13 CP-01 target (pending mentor confirmation)

## Context
Copilot regulatory accuracy is 10/25 live against a BRD target of ≥ 20/25. Retrieval puts the expected document in the top 5 for only 10 of 19 answerable items, capping the score near 16/25 however good the answers are. Plan v3.4 caps added work at ~50 hours.

## Decision
1. **Kept (retrieval first):** deterministic contextual chunk headers on the existing section chunks (boundaries and `chunk_id`s unchanged; one re-ingest), deterministic glossary query rewrite, answerability gate, retrieval ladder report, span-cited answers (single call; the Critic cuts sentences without a valid span).
2. **Reranker on.** The local cross-encoder already built behind ADR 0013 is enabled (user decision 2026-11-18, standing in for the mentor's answer). Results are reported with and without it (KR-03).
3. **Tuning only on the dev split** (`evaluation/retrieval/dev/`, 20 queries never cited by the frozen sets; a test enforces it). The frozen 40 and the 100 items are reported on, never tuned on.
4. **Dual scoring.** *Strict*: the answer cites the gold document. *Supported*: it cites a valid, current, non-superseded document that supports the answer (judge J1 plus a listed human sample). **Strict stays the headline.**
5. **Targets.** Recall@5 ≥ 30/40 on the frozen v1.0 labels (34 stretch). Copilot regulatory **strict ≥ 16/25**, supported reported beside it; false abstain ≤ 3/25; refusal 8/8, injection 8/8, isolation 3/3 unchanged. These may be revised during testing, with the reason recorded in this ADR's log below; BRD ≥ 20/25 is reported as the original target, with the gap explained.
6. **Deferred (future work in the report):** CP-07 intent routing, full two-call CP-08, CP-10 case-aware tools, CP-11 case memory, CP-12 streaming/follow-ups/feedback, A7 guard-model ablation, adaptive red-team round, reversible token vault.
7. **Stretch items cut:** UI-09, UI-10, WC-08, LW-15, VER-06, ONB-07, CP-04 (BUILD_SCOPE "Cut by plan v3.4").

## Consequences
- The report compares strict and supported side by side; a reader can see both.
- The mentor can still overrule the target; this ADR records the decision trail.

## Log
- 2026-11-18: accepted with reranker on and strict ≥ 16/25.
