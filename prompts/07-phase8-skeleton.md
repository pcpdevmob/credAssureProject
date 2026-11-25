# 07 · Phase 8 — walking skeleton

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W1 D4–W2 D1 | Supervisor owner | 03 done (can overlap 05) | Click through the demo case in the reference UI or API docs |

## Paste into the coding tool

```markdown
Run Phase 8 (or /phase 8): Supervisor graph with placeholder agents, Plan span, PLANNER_MODE flag, async stage jobs (202 + job
resource + SSE), Idempotency-Key, loop detection, every /v1 endpoint and each agent's api/ router mounted by the gateway,
/health/live and /health/ready, full-case e2e test with FakeLLM, quota monitor.
Also build scope items: 4, 15, 16, 19, 47, 50 (docs/BUILD_SCOPE.md).
Follow the project rules rules: plan first, tests first, make check green, reviewer subagents, add one progress entry in docs/progress/entries/ (from TEMPLATE.md) and update your module file in docs/progress/modules/, run make progress (never edit PROGRESS.md by hand), commit.
When done, run the evaluation(s): E9, E11 (the tool configuration) and fix every MUST finding.
Done when: Demo case runs end to end with LLM_ENABLED true and false; commit phase-8.
```
