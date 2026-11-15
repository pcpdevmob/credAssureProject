# Retrieval relevance criteria — pooled judgement for labels v1.1 (KR-05)

Written 2026-11-15, **before** any passage was judged. Do not change these criteria once judging starts. If a rule turns
out to be unclear, write the case in your note column and let the adjudicator decide it.

## Who judges
| Role | Owner (CODEOWNERS) | Why |
|---|---|---|
| Judge A | @credassure-owner-name2 | Owns `evaluation/testset`; does not own the copilot or retrieval |
| Judge B | @credassure-owner-name5 | Owns the Critic and ablations; does not own the copilot or retrieval |
| Adjudicator | @credassure-owner-name3 | Decides only the rows where A and B disagree |

The copilot owner (name6) and the co-owner of `packages/retrieval` (name1) do not judge, because their own system is being measured.

## What you are judging
`judging_sheet.csv` lists every distinct passage that any of the 18 retrieval configurations (3 chunkings × 3 retrievers ×
rerank on/off) returned in its top 10 for one of the 40 KR-05 queries. Duplicates are merged and the order is shuffled within
each query. Nothing in the sheet tells you which configuration, which rank or which existing label a passage came from. Some
rows are already labelled relevant in v1.0. You are not told which, and you judge them like any other row.

## The question for every row
> **Could a careful analyst answer this query correctly, for an Indian commercial-bank lender as of 2026-11-15, by citing this
> passage, read on its own?**

Mark **R** (relevant) when the passage, without the rest of its document:
1. states the rule, figure, rate, limit, procedure or definition the query asks for; **or**
2. is the operative provision a correct answer must cite (for example, the paragraph that lays down the rule, even if a
   neighbouring paragraph gives the worked example).

Mark **N** (not relevant) when the passage:
- is on the topic but does not give what the query asks (a heading, table of contents, preamble, scope clause, definitions
  list without the needed term, or a cross-reference such as "see para 12");
- answers a different question about the same subject (for example, the CGTMSE coverage percentage when the query asks for the
  fee);
- would only help together with another passage;
- is boilerplate (site menu, footer, contact block, disclaimer);
- applies only to a different lender type (NBFC, co-operative bank) or another state, or is shown as superseded or not yet in
  force (the filters should have removed these: mark N and say so in your note).

When unsure, mark **N** and write why in the note. Do not leave a row blank.

## Rules of conduct
- Judge alone. Do not discuss rows with the other judge until both sheets are handed in.
- Do not run the search, open the eval reports or look at `queries.jsonl` labels while judging.
- Use only `R` or `N` in `judge_A` / `judge_B`. Notes are free text.
- The adjudicator fills `adjudicated` (R/N) and `adjudicator_note` **only** where `judge_A` ≠ `judge_B`, applying these
  criteria, not their own view of what the system should find.

## What happens next
`make retrieval-merge` checks the sheet and builds `queries.v1.1.jsonl`. The final label is the judges' answer when they agree,
otherwise the adjudicated one. v1.1 = v1.0 labels plus every final **R**; v1.0 is kept unchanged. A v1.0 label the judges
mark N is listed as *disputed* for a human decision and is never removed automatically. Raw agreement and Cohen's kappa
between A and B are reported.
