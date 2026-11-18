# Prerequisites

Quick path: [README §2](../../README.md#2-prerequisites). This page adds the checks and the course-endpoint details.

## Tools
| Tool | Version | Check |
|---|---|---|
| git | any recent | `git --version` |
| uv | latest | `uv --version` |
| Python | 3.12 (managed by uv) | `uv python install 3.12` |
| Node.js + npm | Node 22 LTS (≥ 22.12) | `node -v && npm -v` |
| make, openssl, sqlite3 | system | `make -v` |
| Docker + Compose | optional (Langfuse, containers) | `docker compose version` |
| Ollama | latest (local model) | `ollama --version` |

Use **npm** for the web workspaces. Don't use yarn, and don't run `corepack enable`.
Hardware: a 16 GB Apple Silicon Mac runs `qwen3:8b` on the GPU at an 8K context.

## Course endpoint
Needed only for `MODELS=course` (the graded path, NFR-01).
1. From the course portal, get the chat key, the embeddings key and the two CA certificates (chat and embeddings hosts).
2. Store the certificates outside the repo:
   ```bash
   mkdir -p ~/.credassure/certs && chmod 700 ~/.credassure
   ```
3. Add to `.env` (never to `deploy/env/models-course.env`):
   `LLM_API_KEY`, `EVAL_API_KEY`, `EMBED_API_KEY`, `LLM_CA_CERT=<abs path>`, `EMBED_CA_CERT=<abs path>`.
4. Verify: `make llm-probe MODELS=course`. It checks reachability, context length and guided-JSON support.
5. Chat is limited to about 55 requests a minute and 1,024 output tokens per call; embeddings to 60 a minute.

## Ollama
```bash
ollama --version
OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_KEEP_ALIVE=30m ollama serve   # leave running
make ollama-pull                                                # qwen3:8b + nomic-embed-text, ~5 GB
ollama ps                                                       # expect CONTEXT 8192, 100% GPU
```
If Ollama runs as the menu-bar app, set `OLLAMA_CONTEXT_LENGTH` and `OLLAMA_KEEP_ALIVE` with `launchctl setenv`, then restart the app.
