# Retrieval label widening — silver labels, then human check (KR-05, E8 M1)

Decided 2026-11-15, before any passage was judged (revised the same day: Claude judges first, humans check later). Criteria: [criteria.md](criteria.md) (unchanged except pool depth).

## Pool
`make retrieval-pool` → `pool.jsonl` / `judging_sheet.csv`: the union of every query's **top 5** over all 18 configurations
(3 chunkings × 3 retrievers × rerank on/off), deduplicated to document + section and shuffled within each query.
995 items (9–39 per query). No configuration, rank or v1.0 label is written anywhere.

## Silver labels: blind Claude session (first)
A one-off export writes a blind package **outside the repo** to `../credassure-judging/`:
- `pool.jsonl`: `item_id`, `query_id`, `query`, `title`, `section`, `passage` (full text). No doc_id, configuration,
  rank, score or label.
- **10% duplicates** (100 items, seeded `CREDASSURE_SEED:duplicates`) under new ids J0996–J1095. Each copy is
  placed at a random position in its own query group. The copy → original mapping lives only in
  [duplicates_map.json](duplicates_map.json), never in the package.
- `criteria.md`: copied unchanged (sha256 checked).
- `README.md`: the output schema, one line per item:
  `{"item_id", "judgment": 2|1|0, "confidence": "high"|"low", "reason", "judge": "claude-code-blind"}`.

A separate Claude Code session opened in that folder (no repo access) judges every item. Its `judgments.jsonl`
comes back here as `judgments_claude.jsonl`. The labels are **v1.1-silver**.

**Self-consistency:** binary agreement (2 = R; 1 and 0 = N) over the 100 duplicate pairs. It is reported with the
labels, together with the share of `low`-confidence answers.

## From grades to labels
The criteria are binary. **2 = R; 1 and 0 = N** ("would only help together with another passage" and "when unsure"
are N in criteria.md). The 0–2 grade is kept for a later graded metric (nDCG) but does not change v1.1.

## Human check (later)
- The **25% random sample** (seeded `CREDASSURE_SEED:agreement`, 249 original items, fixed before judging) is
  judged blind with `make judge SAMPLE=0.25`: **Pritish** first (`JUDGE=pritish`), then **Tejas or Abhishek**
  (`JUDGE=tejas` / `JUDGE=abhishek`). Human judges do not see the silver labels or each other's files.
- Cohen's kappa on the binary label, silver vs human, over the sample:
  - **κ ≥ 0.7** → silver labels confirmed; v1.1 drops "silver".
  - **κ < 0.7** → full human judging of all 995 items per criteria.md, with **Suresh adjudicating** the
    disagreements.
- v1.0 labels are never removed automatically; a v1.0 label judged N is listed as disputed for a human decision.

`make judge` reference: one item at a time (query, title, section, first 1,200 characters). Keys `2`/`1`/`0`,
`s` skip, `b` back, `c` criteria, `q` quit. Answers are appended to `judgments_<judge>.jsonl`; the latest answer
per item wins; reruns resume.
