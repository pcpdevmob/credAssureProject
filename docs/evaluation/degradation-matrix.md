# Graceful-degradation matrix (scope #34, P7.4)

What still works when a dependency fails. Every row is injected in `tests/e2e/test_degradation_matrix.py`
(`make check` runs it) on the demo case through the API. "Code outcome" means the gates, the recommended
₹1,42,00,000, the Director route and the ranking `[OF-01-B, OF-01-A]` are unchanged (ARCHITECTURE Q5).

| Fault | How it is injected | Code outcome | Narratives | Copilot | `/v1/health/ready` | Test id |
|---|---|---|---|---|---|---|
| F1 Model disabled | `LLM_ENABLED=false` | Unchanged | Templates (ADR 0003 §2) | Exact abstention string | `model: disabled` | `F1_model_disabled` |
| F2 Model endpoint down | Model port raises `LLMError`; breaker open | Unchanged | Templates (ADR 0008) | Exact abstention string | `degraded`, `model: open` | `F2_model_down` |
| F3 Model returns unusable output | Model port answers non-JSON | Unchanged | Templates after repair fails | Exact abstention string | `ok` | `F3_model_garbage` |
| F4 Corpus / vector store missing | `CORPUS_DB` points nowhere | Unchanged | Templates | Exact abstention string (search unavailable, fails closed) | `ok` | `F4_corpus_missing` |

Covered elsewhere (linked from `docs/security/owasp-asi-mapping.md` where relevant):

| Fault | Behaviour | Test |
|---|---|---|
| Run already in progress on the case | Uploads and runs answer 409 `RUN_IN_PROGRESS`; inputs never change under a running stage | `apps/gateway/tests` (run lock tests) |
| Model call timeout | Stage blocker `TIMEOUT`, state saved | `agents/supervisor/tests/test_resilience.py::test_scope23_model_call_timeout_is_a_TIMEOUT_blocker` |
| Model lost mid-stage | Stage re-runs on templates | `agents/supervisor/tests/test_resilience.py::test_scope48_model_lost_mid_stage_reruns_it_on_templates` |
| Token budget spent | Budget blocker; no further calls | `agents/supervisor/tests/test_resilience.py::test_NFR03_spent_budget_is_a_budget_blocker` |
| Rate limit | 429 problem+json with CORS headers | `apps/gateway/tests/test_contract_phase8.py::test_NFR04_over_rate_limit_is_429` |
| Concurrent cases | No lock errors; every case reaches gold | `tests/e2e/test_load_smoke.py` (timing: `make load-smoke`) |
