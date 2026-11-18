# Retrieval dev split (plan v3.4 §8, ADR 0032)

`queries.jsonl` holds 20 queries (D01–D20) used **only for tuning**: the answerability threshold, the glossary rewrite and any retrieval parameter. The frozen 40 (`evaluation/retrieval/v1/`) and the 100-item test set are reported on, never tuned on (CLAUDE.md, plan v3.4).

- Same format as `v1/queries.jsonl`, plus `label_status`.
- Every query targets a current, Indian, commercial-bank-or-all document that **no frozen query, silver label file or test item cites**; `evaluation/tests/test_dev_split.py` enforces this.
- Labels start as `label_status: proposed` at whole-document level (`section_path: ""`, `exact: false`, so any passage of the document counts; `exact: true` with an empty path would match only passages before the first heading — corrected in P4 before any tuning), drafted from manifest titles without reading frozen labels.

## Confirming labels (human step, P0 0.3)
For each query: open the document, confirm it answers the question, narrow `relevant_sections` to the section that does (or keep whole-document if it has no headings), add any second relevant document, then set `label_status: confirmed` and add `"labelled_by": "<name>"`. Replace a query whose document does not answer it. Nobody labels a query for a module they own.

This split is **not frozen**: it can change until P4 starts tuning; after that, changes go in `queries.v2.jsonl`.
