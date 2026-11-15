# Retrieval label widening — single-judge method (KR-05, E8 M1)

Decided 2026-11-15, before any passage was judged. Criteria: [criteria.md](criteria.md) (unchanged except pool depth).

## Pool
`make retrieval-pool` → `pool.jsonl` / `judging_sheet.csv`: the union of every query's **top 5** over all 18 configurations
(3 chunkings × 3 retrievers × rerank on/off), deduplicated to document + section and shuffled within each query.
995 items (9–39 per query). No configuration, rank or v1.0 label is written anywhere.

## Judge
**Single judge: Pritish**, who does not own the copilot or `packages/retrieval`. Resulting labels are
**v1.1-provisional** until the agreement check below passes.

`make judge` (default `JUDGE=pritish`) shows one item at a time: query, document title, section and the first 1,200
characters of the passage. Keys: `2` relevant (answers the query), `1` partially relevant, `0` not relevant,
`s` skip, `b` back, `c` show criteria, `q` quit. Every answer is appended to `judgments_<judge>.jsonl`
(`item_id`, `judge`, `label`, `ts`) immediately; the latest answer per item wins; a rerun resumes at the first
unanswered item.

## From grades to labels
The criteria are binary. **2 = R; 1 and 0 = N** ("would only help together with another passage" and "when unsure"
are N in criteria.md). The 0–2 grade is kept for a later graded metric (nDCG) but does not change v1.1.

## Agreement check
- A **25% random sample** (seeded `CREDASSURE_SEED:agreement`, 249 items, fixed before judging) is judged blind by
  **Tejas or Abhishek**: `make judge JUDGE=tejas SAMPLE=0.25` (or `JUDGE=abhishek`). They do not see Pritish's file.
- Cohen's kappa on the binary label over the sample:
  - **κ ≥ 0.7** → Pritish's labels are kept; v1.1 drops "provisional".
  - **κ < 0.7** → full double judging of all 995 items per criteria.md, with **Suresh adjudicating** the disagreements.
- v1.0 labels are never removed automatically; a v1.0 label judged N is listed as disputed for a human decision.
