# 11 · Phase 7 — retrieval

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W2 D3–4 | Copilot owner | 04 done | Tell Claude if the mentor allowed a local reranker (default none, ADR 0013) |

## Paste into Claude Code

```markdown
Run Phase 7 (or /phase 7) in packages/retrieval: three chunkers, FTS5, Chroma, RRF, reranker or none, filters; retrieval report.
Follow CLAUDE.md rules: plan first, tests first, make check green, reviewer subagents, add one progress entry in docs/progress/entries/ (from TEMPLATE.md) and update your module file in docs/progress/modules/, run make progress (never edit PROGRESS.md by hand), commit.
When done, run the evaluation(s): E8 (retrieval part) (.claude/commands/eval.md) and fix every MUST finding.
Done when: ≥500 docs indexed; ≥34/40 in top 5; commit phase-7.
```
