# 08 · Phase 5 — database, ledger, audit, auth

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W2 D1 | Supervisor owner | 07 done | — |

## Paste into the coding tool

```markdown
Run Phase 5 (or /phase 5) in packages/ledger and packages/security: repositories + unit of work, ledger write and audit event in one
transaction, row_version optimistic concurrency, WAL + busy timeout + per-case run lock, tenant scoping, JWT + roles + maker-checker.
Also build scope items: 22 (DB part), 49 (docs/BUILD_SCOPE.md).
Follow the project rules rules: plan first, tests first, make check green, reviewer subagents, add one progress entry in docs/progress/entries/ (from TEMPLATE.md) and update your module file in docs/progress/modules/, run make progress (never edit PROGRESS.md by hand), commit.
When done, run the evaluation(s): E10 (auth part) (the tool configuration) and fix every MUST finding.
Done when: Isolation 3/3; audit tamper test; commit phase-5.
```
