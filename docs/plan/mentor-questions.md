# Questions for the mentor (plan v3.4 §10)

Answers are recorded with who gave them and when. A user decision stands in for the mentor's answer until the mentor says otherwise; ADRs record the trail.

| # | Question | Answer | By, date | Where recorded |
|---|---|---|---|---|
| 1 | May we enable the local cross-encoder reranker (BAAI/bge-reranker-base, MIT), built but off by ADR 0013? | **Yes** (team decision; mentor to confirm) | Pritish, 2026-11-18 | ADR 0032 §2, ADR 0013 amended |
| 2 | Is a separately frozen safety_v2 suite (40 items, frozen before its first run) acceptable alongside the frozen 100-item set? | Open | — | ADR 0031 (Proposed) |
| 3 | Can the system card sit in an appendix outside the 12-page report? | Open | — | P10 / P12 |
| 4 | Copilot regulatory: keep the BRD target ≥ 20/25, or accept **strict ≥ 16/25 with the supported score reported beside it** (retrieval caps the score near 16/25)? | Team proceeds with strict ≥ 16/25, adjustable during testing; BRD target reported as original | Pritish (delegated to Claude), 2026-11-18 | ADR 0032 §5 |

Also for the mentor (no blocker): the graded course-endpoint run is deferred until the endpoint is agreed; P7 results on the local model are marked provisional.
