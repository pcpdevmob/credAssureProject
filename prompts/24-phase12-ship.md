# 24 · Phase 12 — ship

> **Superseded for plan v3.4 (2026-11-18):** run [37-p10-phase-12-ship-rai-docs.md](37-p10-phase-12-ship-rai-docs.md) instead. It includes this step's scope plus the v3.4 additions. Kept for reference.

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W4 D3–4 | Supervisor owner | 22 done | Record the demo video by W4 D3 (ADR 0015) |

## Paste into Claude Code

```markdown
Run Phase 12 (or /phase 12): Dockerfiles and Compose profiles, replay mode, demo-reset, backup/restore, release bundle with SBOM and
eval report, RUNBOOK.md, MODEL_CARD.md, CONTRIBUTIONS.md, setup and deployment docs complete.
Also build scope items: 3, 17, 18, 37, 38, 41, 45 (docs/BUILD_SCOPE.md).
Follow CLAUDE.md rules: plan first, tests first, make check green, reviewer subagents, add one progress entry in docs/progress/entries/ (from TEMPLATE.md) and update your module file in docs/progress/modules/, run make progress (never edit PROGRESS.md by hand), commit.
When done, run the evaluation(s): E15, E17 (.claude/commands/eval.md) and fix every MUST finding.
Done when: Clean-machine run passes; tag v1.0.0.
```
