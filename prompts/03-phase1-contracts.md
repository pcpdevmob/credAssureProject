# 03 · Phase 1 — shared contract, money, normaliser

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W1 D2 | Supervisor owner + all | 02 done | Approve AgentResult freeze (incl. agent_version) and tenant_id |

## Paste into Claude Code

```markdown
Run Phase 1 (or /phase 1) in packages/core. Add Plan, CriticFinding, error catalogue, blocker catalogue, ports (LLMPort, ToolPort,
LedgerPort, RetrievalPort, ClockPort), agent registry schema and the ADRs for rounding (0010) and excluded multi-agent patterns (0009).
Also build scope items: 8, 9, 21 (schema), 24, 25 (agent_version), 26, 32, 46 (docs/BUILD_SCOPE.md).
Follow CLAUDE.md rules: plan first, tests first, make check green, reviewer subagents, update PROGRESS.md, commit.
When done, run the evaluation(s): E4 (normaliser part) (.claude/commands/eval.md) and fix every MUST finding.
Done when: ≥50 normaliser tests; mypy strict clean; contract-freeze ADR; commit phase-1.
```
