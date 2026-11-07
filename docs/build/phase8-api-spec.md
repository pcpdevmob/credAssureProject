# Phase 8 API spec (tests are written against this; implementation follows)

## App factory and fixtures
- `credassure.gateway.main.create_app(settings: Settings | None = None, *, llm: LLMPort | None = None) -> FastAPI`
- New Settings fields: `case_db: Path = Path("var/case.db")` (env CASE_DB), `seed_password: SecretStr | None` (SEED_PASSWORD),
  `rate_limit: str = "120/minute"` (RATE_LIMIT), `token_quota: int = 2_000_000` (TOKEN_QUOTA), `max_upload_bytes: int = 2_097_152`.
- Test settings: `Settings(_env_file=None, app_env="test", jwt_secret="x"*40, case_db=tmp/"case.db", llm_enabled=<bool>, tracing_enabled=False)`.
- Test DB: `credassure.ledger.seed.seed(db, {"SEED_PASSWORD": "fixture-password-123"})`. This migrates the DB and seeds users from
  data/frozen/v1/users/eval_users.yaml:

  | Username | Role |
  |---|---|
  | demo.preparer | preparer, emp_id E001 |
  | demo.preparer2 | preparer |
  | demo.director | director_finance |
  | demo.vp | vp_finance |
  | demo.evaluator | evaluator |

  Every `user_id` is `"u-<username>"`.
- FakeLLM: `from credassure.llm.fake import FakeLLM`.
  - Constructor: `FakeLLM(replies: Mapping[str, str | list[str]] | None = None, default="ok")`.
  - `.complete(prompt: str, *, name: str = "default") -> str`.
  - `.calls: list[tuple[str, str]]` records (name, prompt).
  - `.circuit_state == "closed"`.
- With `llm_enabled=True` pass `llm=FakeLLM()`; with False pass nothing.
- TestClient runs BackgroundTasks before `post()` returns, so a run is finished when the 202 comes back.

## Errors — RFC 9457
Every 4xx/5xx is `application/problem+json` with `{type, title, status, detail, code, instance}`. Upload and validation
errors also carry `errors: [{field, row, reason}]`. Every response has `X-Request-ID`.

`code` is an `ApiErrorCode` value:

| HTTP | code |
|---|---|
| 401 | UNAUTHENTICATED |
| 403 | FORBIDDEN |
| 404 | NOT_FOUND |
| 409 | CONFLICT, RUN_IN_PROGRESS |
| 413 | PAYLOAD_TOO_LARGE |
| 415 | UNSUPPORTED_MEDIA_TYPE |
| 422 | VALIDATION_FAILED |
| 429 | RATE_LIMITED |
| 501 | NOT_IMPLEMENTED |

## Endpoints (all JSON, bearer token unless noted)

### Auth
- `POST /v1/auth/token` (no auth), body `{username, password}`.
  - 200 `{access_token, token_type:"bearer", expires_in}`; bad credentials → 401.
  - An unknown username still runs one argon2 verify. To test it, monkeypatch `credassure.gateway.routers.auth.verify_password` and count the calls.
- `GET /v1/me` → `{user_id, username, role}`. A user deactivated after login (`UPDATE users SET active=0`) gets 401 on the next request.

### Cases and files
- `POST /v1/cases` (preparer only, else 403), body `{msme_name, order_ref, order_value_paise:int, indicative_amount_paise:int, due_date}`
  → 201 `{case_id ("CA-YYYY-NNNN"), status:"CREATED", row_version, ...}`.
- `GET /v1/cases` → `{items:[case summaries visible to the caller]}`.
- `GET /v1/cases/{id}` → `{case_id, status, current_stage, route, row_version, indicative_amount:{paise,display},
  stages:[{stage, decision, attempt, blockers, question, trace_id}], question, next_action}`.
  A case the caller cannot see → 404, so its existence never leaks.
- `POST /v1/cases/{id}/files?kind=<order|opening_position|costs|receipts|receivables|payables|inventory>`, multipart field `file`.
  Only the preparer who owns the case may upload.
  - Accepted: `.json` / `application/json` and `.csv` / `text/csv`. Anything else → 415.
  - Larger than 2 MB → 413.
  - Invalid content → 422 with `errors:[{field,row,reason}]`. `row` is the 1-based data row for CSV and null for JSON.
  - Success → 201 `{kind, sha256, rows}`.

### Runs and jobs
- `POST /v1/cases/{id}/run` (case preparer only), optional header `Idempotency-Key`.
  - Returns 202 `{job_id, case_id, status, status_url:"/v1/jobs/<id>", events_url:"/v1/jobs/<id>/events"}`.
  - The same key returns the same `job_id`, still with 202.
- Per-step wrappers each start a 202 job for one stage:

  | Endpoint | Stage |
  |---|---|
  | `POST /v1/cases/{id}/readiness` | onboarding |
  | `POST /v1/cases/{id}/assessment` | working_capital |
  | `POST /v1/cases/{id}/proposal` | lendwise |
  | `POST /v1/cases/{id}/verify` | critic |

  If the upstream stage is not GO, the job ends with outcome `PAUSED` and blocker SUP_UPSTREAM_NOT_GO (SUP-03).
- `GET /v1/jobs/{job_id}` → `{job_id, case_id, kind, stage, status, outcome, error}`.
  - `status` is one of queued, running, succeeded, failed or abandoned.
  - `outcome` is the case status after the run, for example AWAITING_APPROVAL, PAUSED, HELD or FAILED.
- `GET /v1/jobs/{job_id}/events` → `text/event-stream`.
  - One `event: stage` per stage run, with data JSON `{stage, decision, attempt}`.
  - The last event is `event: end` with data `{status, outcome}`.
- Case lifecycle with placeholder agents, all GO: ONBOARDING → WORKING_CAPITAL → LENDWISE → CRITIC → routing.
  The placeholder WC writes `wc.recommended_amount` = 14200000 (₹1.42 cr), which routes to `director_finance` with status AWAITING_APPROVAL.

### Results, chat and decisions
- `GET /v1/cases/{id}/funding` → `{recommended_amount:{paise, display}|null, indicative_amount:{paise,display}, facts:[{key,value,unit,version,source_type}]}`.
- `GET /v1/cases/{id}/offers` → `{offers:[], facts:[...]}`.
- `POST /v1/cases/{id}/chat`, body `{message}` → 200 `{answer, citations:[], intent, trace_id}`. With the LLM off, the answer contains "unavailable".
- `GET /v1/inbox` (director or VP) → `{items:[cases awaiting this role]}`; a preparer gets 403.
- `GET /v1/cases/{id}/inbox` → the pending decision for the routed approver.
- `POST /v1/cases/{id}/decision`, body `{decision: approve|reject|return, return_stage?: stage, comment: str, expected_version: int}`
  → 200 `{status, approval_id}`. Refusals:
  - a preparer on their own case → 403;
  - a director on a case routed to vp_finance or HELD → 403, or 404 when the case is not visible;
  - an evaluator → 403;
  - a stale `expected_version` → 409 CONFLICT.

  A return sets status RETURNED and `current_stage = return_stage`. The next `/run` re-runs only from that stage; earlier stage attempts stay unchanged.
- `GET /v1/cases/{id}/report?fmt=md|html` → text. It contains every trace_id and internal-approval wording ("not loan acceptance").
- `GET /v1/cases/{id}/audit` (evaluator only) → `{events:[{seq,event_type,actor,ts}], chain_ok: bool, broken: [int]}`.

### Admin, eval and health
- `POST /v1/admin/config` (evaluator), body `{key:"boundary_rule", value:"hold|director|vp"}` → 200; any other role → 403.
- `POST /v1/eval/runs` and `GET /v1/eval/runs/{id}` → 501 NOT_IMPLEMENTED for an evaluator, 403 for anyone else.
- `GET /v1/health/live` (no auth) → `{status:"ok"}`.
- `GET /v1/health/ready` (no auth) → `{status: "ok"|"degraded", checks:{db, chroma, model, quota}}`, where:
  - `db` is "ok" or "error";
  - `chroma` is "not_configured" until Phase 7;
  - `model` is "closed", "open" or "disabled";
  - `quota` is `{used, limit, level}`, with `level` one of "ok", "warn_70", "warn_90" or "exhausted".
- Quota rules:
  - `quota.used` is the sum of `tokens_used` over stage runs.
  - At 70% the level is warn_70; at 90% it is warn_90.
  - At or above 70%, the 202 run response carries the header `X-Quota-Warning: warn_70|warn_90`.
- Rate limit: going over `rate_limit` → 429 problem RATE_LIMITED.

## Agent routers (mounted at /v1/agents/<name>; auth via gateway)
- **onboarding, working-capital, lendwise, critic:**
  - `GET /card` → `{name, version, ...}`;
  - `GET /health`;
  - `POST /cases/{id}/run` → 202 job for that stage only, through the Supervisor;
  - `GET /cases/{id}/result` → the latest AgentResult JSON, or 404.
- **supervisor:** `GET /cases/{id}/plan` → Plan JSON (stages list); `GET /cases/{id}/result`; `POST /cases/{id}/stages/{stage}/retry` → 501.
- **lendwise:** `POST /cases/{id}/negotiate` → 501.
- **copilot:** `POST /cases/{id}/chat` behaves like the core chat route.
- An unauthenticated request to any case route → 401.

## Ledger additions (packages/ledger)
- **Audit head:**
  - Table `audit_head(tenant_id PK, seq, hash)` holds one row per tenant. It is upserted in the same transaction as each `writes.append_audit`.
  - `reads.audit_head(s, tenant_id)` returns that row.
  - `reads.verify_chain(s)` also reports a failure, such as `[head.seq]`, when the newest rows were cut.
  - Test:
    1. Drop the triggers on audit_log through raw sqlite3 (`SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='audit_log'`).
    2. Run `DELETE FROM audit_log WHERE seq=(SELECT max(seq) FROM audit_log)`.
    3. `verify_chain` must return a non-empty list.
- **Run lock:**
  - `session.HEARTBEAT = timedelta(seconds=30)` and `session.STALE_LOCK == 3 * HEARTBEAT`.
  - `session.heartbeat(engine, case_id, run_id) -> bool` refreshes `acquired_at` and returns False if the lock was lost.
  - `run_lock` takes over a lock only when it is older than STALE_LOCK.
- **Jobs:**
  - `writes.create_job(s, *, tenant_id, case_id, kind, stage, idempotency_key, actor) -> Job` returns the existing job when (tenant_id, case_id, idempotency_key) already exists.
  - `writes.update_job(s, job_id, *, status, outcome=None, error=None)`.

## Phase 8a — Python contracts (Supervisor, tools, tracing, LLM fake, ledger adapter)

### `credassure.agents.supervisor.graph`
```python
@dataclass
class RunOutcome:
    status: str              # PAUSED | AWAITING_APPROVAL | HELD | FAILED | APPROVED | REJECTED | RETURNED
    stage: Stage | None      # the stage that paused or failed (None otherwise)
    question: str | None     # exactly one focused question when PAUSED (SUP-06)
    results: dict[Stage, AgentResult]

Recheck = Callable[[AgentResult, LedgerPort], list[Blocker]]   # empty list = check passes

class Supervisor:
    def __init__(self, *, agents: Mapping[Stage, StageAgent], store: SupervisorStore, ledger: LedgerPort,
                 tools: Callable[[AgentName], ToolPort], llm: LLMPort | None, clock: ClockPort,
                 checkpointer: BaseCheckpointSaver, tenant_id: str = "default",
                 rechecks: Mapping[Stage, Recheck] | None = None,   # None → default_rechecks()
                 max_steps: int = 10, token_cap: int = 6000,
                 planner_mode: Literal["fixed", "llm_proposes"] = "fixed", ablation: str | None = None,
                 boundary_rule: Literal["hold", "director", "vp"] = "hold") -> None
    def plan(self, case_id: str) -> Plan
    def run(self, case_id: str, *, stage: Stage | None = None) -> RunOutcome
    def decide(self, case_id: str, *, decision: Literal["approve", "reject", "return"],
               return_stage: Stage | None = None) -> RunOutcome
```
Behaviour:
- Plan order ONBOARDING → WORKING_CAPITAL → LENDWISE → CRITIC, then routing (code). No stage skipped (SUP-01).
- Each stage gets a fresh `StageContext(case_id=<injected>, tenant_id, stage, trace_id, ledger, tools(AgentName), llm, clock)`;
  case_id is always the run's case_id (SUP-08). Store calls: `stage_started` → `stage_finished` per attempt.
- SUP-04: an agent output that is not a valid `AgentResult` (or has another case_id/stage) is re-requested up to 2 more times
  (3 calls total), then the stage is ERROR with blocker `SUP_SCHEMA_INVALID`.
- SUP-07: `steps_used > max_steps` or `tokens_used > token_cap` → ERROR with `SUP_BUDGET_EXCEEDED`; outcome FAILED; state saved.
- #4: `credassure.tools.runner.LoopDetected` raised inside an agent → ERROR (outcome FAILED, blocker SUP_BUDGET_EXCEEDED,
  message mentions "loop"). Any other exception from an agent → ERROR, outcome FAILED.
- SUP-05: on GO, run `rechecks[stage](result, ledger)`; non-empty → decision overridden to NO_GO, those blockers added,
  `store.audit(case_id, "GATE_OVERRIDE", {...})`. `ablation == "A4"` skips the re-check (scope #1).
  `default_rechecks()` (module function) for every stage: any blocker whose `blocker_effect` is GATE → fail; every
  `EvidenceRef(kind="ledger_fact")` must exist in the ledger (`ledger.get(case_id, ref_id) is not None`).
- NO_GO / NEEDS_INPUT → outcome PAUSED, `stage` set, `question` = result.question or first blocker message;
  `store.set_state(case_id, status="PAUSED", current_stage=stage)`. ERROR → FAILED, `set_state(status="FAILED", ...)`.
- SUP-06: calling `run()` again re-invokes only the first stage that is not GO; earlier GO stages are not called again.
- SUP-03: `run(case_id, stage=X)` with any earlier plan stage not GO → PAUSED, stage X, blocker `SUP_UPSTREAM_NOT_GO`,
  agent X not called.
- Routing after CRITIC GO: read `ledger.get(case_id, "wc.recommended_amount")` (rupees, Decimal text) →
  `engines.routing.route(amount, boundary_rule)` → `store.route(case_id, route)`. Outcome AWAITING_APPROVAL
  (director_finance / vp_finance) or HELD. Missing amount → FAILED. Then the graph waits on a LangGraph `interrupt()`.
- `decide()` resumes the interrupt: approve → APPROVED, reject → REJECTED, return(stage) → RETURNED and the results of that
  stage and every later stage are cleared, so the next `run()` restarts from that stage only. `decide()` does not write
  the case status (the ledger's `record_decision` already did).
- #19: `plan()` emits a tracing span "plan" with attrs `{case_id, mode, stages, accepted}`. `planner_mode="llm_proposes"`
  calls `llm.complete(prompt, name="sup_plan")`, expects a JSON list of stage names; accepted only if it equals the fixed
  order; otherwise (or llm None / invalid JSON) the fixed plan is used, `accepted=False`, mode "fixed".
- Tests use `langgraph.checkpoint.memory.InMemorySaver()` and in-memory fakes for store/ledger/tools/clock.

### `credassure.tools.runner`
`class LoopDetected(RuntimeError)`. `ToolRunner(agent: AgentName | str, handlers: Mapping[str, Callable[..., Any]])`
with `call(name, case_id, args=None)`: checks `credassure.tools.registry.authorize(agent, name, case_id=case_id)`
(raises `RegistryError` when not allowed), then calls `handlers[name](case_id=case_id, **args)`. A second call with the
same name and the same canonical args (JSON, sorted keys) in the same runner raises `LoopDetected`. A handler raising
`ToolError` is retried up to 2 times (3 attempts) before the error propagates (SUP-07).

### `credassure.observability.tracing`
`span(name: str, **attrs) -> ContextManager[None]` logs a structured line (and a Langfuse span when configured).
`capture() -> ContextManager[list[dict]]` collects `{"name": ..., **attrs}` for every span opened inside it (tests).

### `credassure.llm.fake.FakeLLM` (see above)

### `credassure.ledger.store.SqlLedger(engine, tenant_id: str, actor: str = "supervisor")`
Implements `LedgerPort` (get/put_fact; put_fact returns the new version, source_type/source_ref recorded, input_hash
sha256 of the value) and `SupervisorStore` (stage_started inserts a `stage_runs` row with attempt = previous attempts + 1;
stage_finished writes decision/result_json/trace_id/ended_at and audits STAGE_COMPLETED; set_state updates
cases.status/current_stage; audit appends to the chain; route delegates to `writes.route_case`). Each call is its own
transaction.

## Phase 8b — tracing exporter contract (`credassure.gateway.tracing`)
- `mask(data: Any) -> Any`: recursive copy where every string is passed through
  `credassure.observability.log.default_redact` (dict keys and values, lists, tuples); non-strings unchanged.
- `make_exporter(client: Any) -> Callable[[str, dict[str, Any]], None]`: each call does
  `client.start_observation(name=name, as_type="span", metadata=mask(attrs)).end()`. Any exception from the client is
  logged and swallowed (a failing tracer never breaks a request).
- `configure(settings: Settings, client_factory: Callable[..., Any] | None = None) -> bool`: installs the exporter via
  `credassure.observability.tracing.set_exporter` only when `settings.tracing_enabled` and both Langfuse keys are set
  (returns True); otherwise uninstalls it (`set_exporter(None)`) and returns False. `client_factory` defaults to
  `langfuse.Langfuse` and is called with `public_key, secret_key, host, mask`.
- `create_app(...)` calls `configure(settings)`. With tracing off every route still works.
