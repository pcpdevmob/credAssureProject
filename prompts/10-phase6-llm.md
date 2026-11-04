# 10 · Phase 6 — model layer and guardrails

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W2 D2–3 | Critic owner + Supervisor owner | 03 done | — |

## Paste into Claude Code

```markdown
Run Phase 6 (or /phase 6) in packages/llm and packages/security: client, structured output + repair, prompt registry, cache,
budget, rate limiter, 30 s timeouts with cancellation, circuit breaker with template fallback (ADR 0008), PII redaction,
spotlighting, injection scanner; CI job that runs the fast eval subset when prompts change.
Also build scope items: 22 (limiter), 23, 36, 48 (docs/BUILD_SCOPE.md).
Follow CLAUDE.md rules: plan first, tests first, make check green, reviewer subagents, update PROGRESS.md, commit.
When done, run the evaluation(s): E4 (.claude/commands/eval.md) and fix every MUST finding.
Done when: Tests pass without network; commit phase-6.
```
