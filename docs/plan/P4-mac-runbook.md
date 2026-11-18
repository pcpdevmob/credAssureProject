# P4 on the Mac: re-ingest and the retrieval ladder

The P4 code (contextual headers, glossary rewrite, answerability gate, ladder script) is built and tested
without a corpus. These steps need the ingested corpus, Ollama embeddings and the reranker, so they run on
the Mac. Prerequisite: the 20 dev-split labels are confirmed (`evaluation/retrieval/dev/README.md`).
Never read the frozen 40 labels to choose a setting; the ladder reports them only.

```bash
git pull                                   # on feature/LendWise after #5 and the P4 PR merge
uv sync --all-packages --locked --extra rerank
# Rung 0: current index, no rewrite, no reranker
make retrieval-ladder RUNG=0 LABEL=baseline
# Rung 1: one re-ingest with contextual headers (chunk ids and stored text do not change)
RETRIEVAL_CONTEXT_HEADERS=true make ingest
RETRIEVAL_CONTEXT_HEADERS=true make retrieval-ladder RUNG=1 LABEL=headers
# Rung 2: + glossary rewrite
RETRIEVAL_CONTEXT_HEADERS=true make retrieval-ladder RUNG=2 LABEL=headers+glossary REWRITE=1
# Rung 3: + reranker (ADR 0032: on)
RETRIEVAL_CONTEXT_HEADERS=true make retrieval-ladder RUNG=3 LABEL=headers+glossary+rerank REWRITE=1 RERANK=1
# Answerability threshold from the dev split only
RETRIEVAL_QUERY_REWRITE=true make retrieval-ladder CURVE=1
make retrieval-ladder REPORT=1              # evaluation/reports/retrieval-ladder-<date>.md
```

Then set the chosen values in `deploy/env/*.env.example` and the local dotenv file
(`RETRIEVAL_QUERY_REWRITE=true`, `ANSWERABILITY_THRESHOLD=<chosen>`, `RERANKER=local_cross_encoder`), keep
`RETRIEVAL_CONTEXT_HEADERS=true` for every later ingest, and re-run `make retrieval-eval` for the full
KR-05 table. Exit checks: recall@5 ≥ 30/40 on frozen v1.0 labels (or the gap explained in the report),
false abstain ≤ 3/25 on the regulatory items (reported, not tuned), no frozen file changed.
