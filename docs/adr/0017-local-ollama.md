# ADR 0017 — Local default model: Ollama, Llama 3.1 8B

Status: Accepted · 2026-11-05 · Approved by the project owner (Pritish) · Does not amend BRD NFR-01

## Context
NFR-01 says the product runs only on the course's ≤8B chat and embeddings endpoints. Those endpoints are not needed to develop or rehearse. The gateway talks to any OpenAI-compatible URL (`LLM_BASE_URL`, `EMBED_BASE_URL`), so a local server can stand in without a second client.

## Decision
- Dev and demo default to [Ollama](https://ollama.com) on `http://localhost:11434/v1` (compose: `http://ollama:11434/v1`).
- Chat model: `llama3.1:8b` (Llama 3.1 8B Instruct, about 4.9 GB). It is inside the ≤8B limit.
- Embeddings model: `nomic-embed-text` on the same server. Llama 3.1 8B does not produce embeddings. Changing the embeddings model later requires a re-index, because the vector size changes.
- Context is 8192 tokens (`LLM_CONTEXT_TOKENS` and `OLLAMA_CONTEXT_LENGTH`), not Llama 3.1's 128k default, so the model fits a normal laptop and prompts stay inside NFR-02.
- `LLM_API_KEY=ollama`. Ollama ignores the key; the OpenAI SDK refuses an empty one.
- `LLM_SUPPORTS_GUIDED_JSON` stays `false` until Phase 6 probes Ollama's JSON mode.
- Graded evaluation uses the course endpoint. Set `LLM_BASE_URL`, `LLM_MODEL`, `EMBED_BASE_URL` and `EMBED_MODEL` to the course values. No code change.
- Amendment 2026-11-15: the course embeddings endpoint serves `bge-small-en-v1.5` (384 dimensions, at most 16 texts per request, 512 model tokens each) behind a self-signed CA. Set `EMBED_CA_CERT` to the CA file, keep `EMBED_BATCH=16` and index into a fresh `CHROMA_PATH`; KR-05 is reported on this embedder.

## Consequences
- `make ollama-pull` downloads both models (about 5 GB). It is not part of `make check` or CI.
- The Phase 6 LLM client reads these settings and needs no Ollama-specific code.
- A result measured on `llama3.1:8b` is not a result on the course model. Eval reports must name the model (scope #13).
