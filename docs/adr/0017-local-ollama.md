# ADR 0017 — Local default model: Ollama (Qwen3 8B since 2026-11-15; was Llama 3.1 8B)

Status: Accepted (amended by ADR 0036: local profile is the evaluated path) · 2026-11-05 · Approved by the project owner (Pritish) · Does not amend BRD NFR-01

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
- Amendment 2026-11-15 (chat): the course model is `Qwen/Qwen3-8B`; groups 016-030 use `https://103.42.50.41:1032/v1` with CA `vm06-ca.crt` (`LLM_CA_CERT`). The local default moves from `llama3.1:8b` to `qwen3:8b`, so local results come from the same model family as graded results. Qwen3 thinks by default; `LLM_DISABLE_THINKING=true` sends `chat_template_kwargs.enable_thinking=false` and strips any `<think>` block. Course limits: 1 active request per key, 60 per minute (`LLM_RATE_PER_MINUTE=55`), 8192 tokens in+out, 1024 output max (`LLM_MAX_TOKENS`). The endpoint serves no embeddings.
- Amendment 2026-11-15: the course embeddings endpoint serves `bge-small-en-v1.5` (384 dimensions, at most 16 texts per request, 512 model tokens each) behind a self-signed CA. Set `EMBED_CA_CERT` to the CA file, keep `EMBED_BATCH=16` and index into a fresh `CHROMA_PATH`; KR-05 is reported on this embedder. Groups use `https://103.42.50.41:1035/v1` with CA `vm02-ca.crt` and the shared embedding key (`EMBED_API_KEY`, distinct from the chat key).
- Amendment 2026-11-15 (switch): `make <target> MODELS=local|course` (default `local`) loads `deploy/env/models-<MODELS>.env` after the dotenv file. Integrate end to end on `local` (Ollama `qwen3:8b` + in-process bge-small); switch to `course` for graded runs. Profiles hold no keys or CA paths (test-enforced); each uses its own `CHROMA_PATH`.
- Amendment 2026-11-15 (local embeddings): `EMBED_BASE_URL=local` runs `BAAI/bge-small-en-v1.5` in-process with `sentence-transformers` (already a retrieval dependency for the reranker). Same model and 384-dim space as the course endpoint, no quota used; the distinct model id keeps its cache and index keys apart. `nomic-embed-text` stays available but its results are not comparable with KR-05.

## Consequences
- `make ollama-pull` downloads both models (about 5 GB). It is not part of `make check` or CI.
- The Phase 6 LLM client reads these settings and needs no Ollama-specific code.
- A result measured on `llama3.1:8b` is not a result on the course model. Eval reports must name the model (scope #13).
