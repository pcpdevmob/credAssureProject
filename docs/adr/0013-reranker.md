# ADR 0013 — Reranker
Status: Accepted · 2026-11-04 · **Amended by [ADR 0032](0032-copilot-v2-scope-and-v34-cuts.md) (2026-11-18): reranker on (user decision)**
Decision: core configuration runs with `RERANKER=none` so retrieval never depends on an approval. If the mentor allows local models,
`RERANKER=local_cross_encoder` (BAAI/bge-reranker-base, MIT) is enabled. Both settings are reported in the retrieval ablation; the
better-scoring permitted setting becomes the demo default.

## Update 2026-11-14 (Phase 7)
The mentor approved the local cross-encoder. `RERANKER=local_cross_encoder` loads `BAAI/bge-reranker-base` through the
optional `rerank` extra of `credassure-retrieval` (`uv sync --all-packages --extra rerank`); nothing imports it when the
setting is `none`. It rescores the RRF top 30 and keeps the top 5. The model is pinned to commit
`2cfc18c9415c912f9d8155881c133215df768a70` (`RERANKER_REVISION`); remote code stays off. The default stays `none` until the retrieval report
(`evaluation/reports/retrieval-<date>.md`) shows which permitted setting scores better; that setting then becomes the demo
default. `llm_pointwise` is not built: with the cross-encoder approved it is not needed, and the setting is refused.
