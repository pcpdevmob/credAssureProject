# 20 · Phase 10 — reports, approvals, explainability

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W3 D3–5 | Supervisor owner + WC owner | 16–18 done | — |

## Paste into Claude Code

```markdown
Run Phase 10 (or /phase 10) but build no Streamlit pages (React replaces them): approvals API with step-up flag, report rendering
and versioning/staleness, lineage endpoint, delete-case with audit tombstone, contract tests, Schemathesis fuzzing.
Also build scope items: 6, 33, 39, 51 (docs/BUILD_SCOPE.md).
Follow CLAUDE.md rules: plan first, tests first, make check green, reviewer subagents, add one progress entry in docs/progress/entries/ (from TEMPLATE.md) and update your module file in docs/progress/modules/, run make progress (never edit PROGRESS.md by hand), commit.
When done, run the evaluation(s): E10, E17 (items due) (.claude/commands/eval.md) and fix every MUST finding.
Done when: Contract and fuzz tests pass; commit phase-10.
```
