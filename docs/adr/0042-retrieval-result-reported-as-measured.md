# ADR 0042 — Retrieval is reported as measured on the frozen labels (22/40); the miss is accepted

Status: Proposed (architect recommendation D1, human review H5; the team confirms or overturns) · Date: 2026-11-24 ·
BRD §13 (retrieval target 34/40), plan v3.4 P4 exit check (≥ 30/40) · Scope #60–#63 · Relates to ADR 0032, ADR 0013

## Context
The shipped retrieval configuration (contextual headers + glossary rewrite, reranker used for the answerability score
only) was chosen on the dev split, as the tuning rule requires. On the frozen 40 queries (v1.0 labels) it scores
recall@5 **22/40**; the headers-only rung scored 25/40 and was not shipped, because it was worse on the dev split
(16/20 against 17/20). Both targets are missed (`evaluation/reports/retrieval-ladder-2026-11-18.md`).

Two ways to make the number look better were available and are refused here:
- choose the configuration by its frozen-set score (25/40): that is tuning on the frozen set;
- relabel the frozen 40. The v1.0 labels look biased towards the documents the first search configuration returned
  (Claude-judged "silver" labels gave 35/40 earlier), but relabelling after seeing results is the same fault.

## Decision
1. The report states recall@5 **22/40** on the frozen v1.0 labels for the shipped configuration, with the full ladder
   (23, 25, 22, 24 of 40) and the dev-split figures (13, 16, 17, 11 of 20) beside it. The targets are reported as missed.
2. The frozen 40 queries and their labels are not changed. Silver labels may appear only as an unvalidated side
   analysis, named as such.
3. The retrieval human judging (249-item sample and 72 disputed labels, H23) is descoped (D3); no claim rests on it.
4. What the miss costs is shown where it matters: the oracle-context run (gold passages handed to the copilot) passes
   8–10 of 19 answerable regulatory items against 6–8 with real search, so search is not the main limit on answers.

## Consequences
- The BRD retrieval target stays unmet in the scorecard; the reader sees why the shipped configuration was still chosen.
- A later, independently labelled query set (v2, with an ADR) is the only route to a different retrieval number.
