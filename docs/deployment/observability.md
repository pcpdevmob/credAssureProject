# Observability

ARCHITECTURE §8.8. Four signals, all local to the machine: no third-party crash tracker, so case data never leaves it
(SYSTEM_CARD §11). Owner: Abhishek (observability package).

| Signal | Where | Answers |
|---|---|---|
| Structured logs | stdout, one JSON object per line | What happened in this request, with which case, trace and stage |
| Traces | Langfuse (self-hosted, ADR 0016) | What the agents and the model did in this case run, step by step |
| Metrics | `GET /v1/metrics` (Prometheus text) | How many requests, how fast, how many failed; how the model calls went |
| Audit log | `case.db`, hash-chained | Who decided what, from which figures (OBJ-08); the record, not a debugging aid |

## Logs
- Every line is JSON: `ts`, `level`, `logger`, `message`, plus `request_id`, `tenant_id`, `case_id`, `trace_id`, `agent`,
  `stage` and any extra fields (`packages/observability/.../log.py`).
- Every string is redacted before it is written (Aadhaar, PAN, account numbers, phone, email; PII v2 in the gateway).
- `LOG_LEVEL` (default `INFO`) sets the level. `uvicorn` access and error logs are routed through the same formatter.

## Request IDs: from a user's screen to the log line
1. The gateway gives every request an id and returns it as `X-Request-ID`.
2. Every problem+json error body also carries it as `request_id`, including server errors (500), so the web app shows
   **Request ID** under the error banner and **Reference** on the crash screen.
3. Ask the user for that id, then search the log: `grep <request_id>` finds the request, the unhandled-error stack trace
   (logger `credassure.gateway`, message `unhandled error`) and any browser report about it (logger `credassure.client`, field `client_request_id`).
4. A model or stage step inside that request carries a `trace_id`; open it in Langfuse.

## Crashes and errors
| Where it fails | What the user sees | What is recorded |
|---|---|---|
| Server, handled (validation, auth, conflict…) | Banner: what happened, how to fix it, the request id | JSON log line; `credassure_http_requests_total{status="4xx"}` |
| Server, unhandled | "Something went wrong on the server" + request id; never a stack trace | Stack trace at ERROR with the request id; `credassure_unhandled_errors_total` |
| Browser, a page crashes | Crash screen with **Try again**, **Go to dashboard** and a reference | `POST /v1/client-errors` (kind `render`) → redacted WARNING line; `credassure_client_errors_total` |
| Browser, uncaught error or rejected promise | Nothing changes on screen | Same report (kind `error` / `unhandledrejection`) |
| Model endpoint | Template narratives; copilot unavailable notice | `credassure_llm_calls_total{outcome="unavailable"\|"timeout"\|...}`; breaker state in `/v1/health/ready` |

Browser reports are sent only from a signed-in session, at most 10 distinct ones per page load, without the query string
of the page (case ids and filters stay out), capped in size, and redacted again by the gateway. The gateway accepts at most
10 a minute per user (429 after that) and logs them at WARNING with the user id, so a flood is visible and attributable. They never reach the model,
the ledger or the audit log.

## Metrics
`GET /v1/metrics` (evaluator token) returns Prometheus text:

| Metric | Labels |
|---|---|
| `credassure_http_requests_total` | `method`, `route` (template such as `/v1/cases/{case_id}`, never a raw id), `status` |
| `credassure_http_request_duration_seconds` (histogram) | `method`, `route` |
| `credassure_llm_calls_total` | `prompt`, `outcome` (`ok`, `timeout`, `budget`, `unavailable`, `error`, `exception`) |
| `credassure_llm_call_seconds_total` | `prompt` |
| `credassure_client_errors_total` | `kind` |
| `credassure_unhandled_errors_total` | — |

Counters are per gateway process and reset on restart. Access tokens expire after 30 minutes, so a long-running
Prometheus scrape needs a sidecar that signs in as the evaluator; for the prototype a manual look is enough:
```bash
TOKEN=...   # an evaluator's access token
curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/v1/metrics | grep -E 'status="5|outcome="(timeout|unavailable)'
```
Per-stage tokens, cost and Critic fallback rate per evaluation item are in the harness results (`make eval`,
`docs/evaluation/how-to-run.md`), not in these counters.

## Langfuse
- On when `TRACING_ENABLED=true` and `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are set (`make up` starts it; README §7).
- One trace per case run and per evaluation item. Spans: the plan, each stage, each tool call, each guardrail decision,
  each model call with OpenTelemetry GenAI attributes (`gen_ai.request.model`, `gen_ai.usage.input_tokens` /
  `output_tokens`) plus the prompt name and version.
- Every span is redacted before export (`apps/gateway/.../tracing.py` `mask`). An export failure is logged and ignored: a
  request never fails because tracing did.

## Health
`GET /v1/health/live` (process up) and `/v1/health/ready`: database, model (`closed`, `open`, `half_open`, `replay`,
`disabled`) and quota (`ok`, `warn_70`, `warn_90`, `exhausted`). The web app uses `model` to show the copilot-unavailable notice.
What to do when one turns red: [RUNBOOK.md](RUNBOOK.md).
