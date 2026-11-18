# 22 · Phase 11 — evaluation, ablations, red-team

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W4 D1–3 | Critic owner + Onboarding owner | 21 done | Label the 20% judge-calibration sample |

## Paste into Claude Code

```markdown
Run Phase 11 (or /phase 11): harness through the API, cost per item, failure-class tagging, judge J1 with calibration (ADR 0014: kappa < 0.7 → human scoring),
ablations A1–A5, red-team log, degradation matrix with fault flags, load smoke test.
Also build scope items: 5, 11, 12, 34, 35 (docs/BUILD_SCOPE.md).
Follow CLAUDE.md rules: plan first, tests first, make check green, reviewer subagents, add one progress entry in docs/progress/entries/ (from TEMPLATE.md) and update your module file in docs/progress/modules/, run make progress (never edit PROGRESS.md by hand), commit.
When done, run the evaluation(s): E12, E13, E14, E16 (.claude/commands/eval.md) and fix every MUST finding.
Done when: ≥92/100 and above baseline; commit phase-11.
```
