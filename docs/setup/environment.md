# Environment variables

TODO owner: [Name 1].

## Required
| Variable | Used by | Meaning |
|---|---|---|
| `CORPUS_CONTACT_EMAIL` | `make corpus-harvest`, `make corpus-download` | Optional. Adds `; contact: <email>` to the scripted User-Agent (ADR 0020). Takes precedence over `CORPUS_CONTACT_URL`. If set but not a valid address, the commands stop. Set it in `.env`; never hard-code it. |
| `CORPUS_CONTACT_URL` | `make corpus-harvest`, `make corpus-download` | Optional. Used when no email is set: adds `; +<url>` (http or https) to the User-Agent. With neither set, the User-Agent is `CredAssure-capstone/1.0 (IIT KGP academic project)`. |

## Model
## Tracing
| `TENANT_ID` | gateway, `make run-api`, `make db`, `make demo-reset` | Tenant of this gateway process. `make run-api`, `make db` and `make demo-reset` set `demo` (the dev/demo database `var/case.db`); an exported value wins over `--env-file`. |
| `CHROMA_PATH` | `make ingest`, copilot search | Vector store directory (default `var/chroma`). The copilot uses the same store and `EMBED_*` embedder as the ingest. |
| `COPILOT_SEARCH_MODE` | copilot search | `hybrid` (default: BM25 + dense, RRF) or `keyword` (BM25 only; tests, or no vector store). |
