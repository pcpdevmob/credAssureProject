# ADR 0013 — Reranker
Status: Accepted · 2026-11-04
Decision: core configuration runs with `RERANKER=none` so retrieval never depends on an approval. If the mentor allows local models,
`RERANKER=local_cross_encoder` (BAAI/bge-reranker-base, MIT) is enabled. Both settings are reported in the retrieval ablation; the
better-scoring permitted setting becomes the demo default.
