# 10 · Phase 6 — model layer and guardrails

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W2 D2–3 | Critic owner + Supervisor owner | 03 done | — |

## Paste into the coding tool

```markdown
Run Phase 6 (or /phase 6) in packages/llm and packages/security: client, structured output + repair, prompt registry, cache,
budget, rate limiter, 30 s timeouts with cancellation, circuit breaker with template fallback (ADR 0008), PII redaction,
spotlighting, injection scanner; CI job that runs the fast eval subset when prompts change.
Also build scope items: 22 (limiter), 23, 36, 48 (docs/BUILD_SCOPE.md).
Follow the project rules rules: plan first, tests first, make check green, reviewer subagents, add one progress entry in docs/progress/entries/ (from TEMPLATE.md) and update your module file in docs/progress/modules/, run make progress (never edit PROGRESS.md by hand), commit.
When done, run the evaluation(s): E4 (the tool configuration) and fix every MUST finding.
Done when: Tests pass without network; commit phase-6.
```
