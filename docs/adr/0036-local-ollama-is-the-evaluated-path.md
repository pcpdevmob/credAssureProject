# ADR 0036 — Local Ollama (qwen3:8b) is the evaluated path; the course endpoint is not used

Status: Accepted (user decision 2026-11-19) · Date: 2026-11-19 · Amends ADR 0017 ("Graded evaluation uses the course
endpoint") · BRD NFR-01 (≤8B kept; "provided endpoints" changed) · Scope #13

## Context
ADR 0017 made local Ollama the development default and the course endpoint the graded path. The course chat model is
`Qwen/Qwen3-8B` and its embeddings are `bge-small-en-v1.5`; since 2026-11-15 the local profile (`MODELS=local`) uses the
same model family (`qwen3:8b` on Ollama) and the same embedder in-process (`EMBED_BASE_URL=local`). The G4 runs
(2026-11-18/19) were all made on the local profile at an 8192-token context. On 2026-11-19 the project owner decided
not to use the course endpoint.

## Decision
1. **The evaluated path is the local profile:** Ollama `qwen3:8b` at `OLLAMA_CONTEXT_LENGTH=8192`, thinking off
   (`LLM_DISABLE_THINKING=true`), bge-small embeddings in-process, `bge-reranker-base` scoring for the answerability
   gate (`RERANK_ORDER=false`). Every G4 number (full run, ablations, judge) comes from this profile, and each run's
   `summary.json` records model, endpoint, prompt versions, corpus lock and `llm_cache: false`.
2. **The ≤8B limit stays** (NFR-01, Track B): no larger or hosted frontier model, no fine-tuning.
3. **Course endpoint support stays in the code, unused.** `MODELS=course`, its profile and the CA settings remain, so
   a graded run on it needs no code change if it is ever required.
4. **Model choice is closed for G4.** Measured on the retrieval dev split only (never the frozen sets):
   `qwen3:8b` cited a relevant document on 10/20 dev queries (4 abstained), `llama3.1:8b` on 5/20 (9 abstained).
   Qwen3 thinking mode is not used: the model only drafts and cites (code calculates, routes and gates), the gain is
   unproven, and it makes calls 3–5 times slower and less reproducible.

## Consequences
- The report names the model as `qwen3:8b` (Ollama, 4-bit quantised build) on a 16 GB Apple Silicon Mac, not the
  course deployment. Scores on the course's full-precision `Qwen/Qwen3-8B` may differ by a few items.
- Latency and throughput figures are for one local machine, not the shared course endpoint and its rate limits.
- `docs/setup` and the setup guide describe the local profile only; course setup stays in `docs/setup/prerequisites.md`.
