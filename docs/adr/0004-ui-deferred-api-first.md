# ADR 0004 — UI deferred; API-first

Status: Accepted · Date: 2026-11-03

## Decision
The UI may change later (existing FinBridge AI UI, React, mobile or Streamlit). The project is built API-first:
- All behaviour lives behind FastAPI (API-01). The UI holds no business logic, calculations, gate logic or role checks.
- `make openapi` exports `openapi.json` at the repo root on every API change; a test fails if it is stale (`test_openapi_current`, run by the pre-push hook; ADR 0027). Any future UI generates its typed client from it.
- `ui/` contains a thin **reference Streamlit client** for demo and evaluation only. It talks to the API through `ui/api_client.py`.
- CORS origins are configured by `UI_ORIGINS` (comma-separated), default `http://localhost:8501`.
- API responses are UI-neutral: stable error format (RFC 9457), money as both `paise` (int) and `display` (₹ Indian grouping) fields, enums as strings.
- Contract tests in `tests/contract/` call every endpoint with the same payloads a UI would send.

Update 2026-11-04: ADR 0005 replaces the Streamlit reference client with a React app in apps/web; every rule above still applies.

## Consequences
Swapping the UI later needs no backend change. Streamlit work is kept minimal (Phase 10 builds only what the demo and the evaluator need).
