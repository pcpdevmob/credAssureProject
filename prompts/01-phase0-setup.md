# 01 · Phase 0 — tooling, CI, config

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W1 D1 | Integration lead | 00 done | Fill .env from .env.example after this step |

## Paste into Claude Code

```markdown
Run Phase 0 from docs/PHASE_PROMPTS.md (or /phase 0). Include settings validation, structured JSON logging, environment profiles
(dev/test/demo), CODEOWNERS, PR template, ADR index and C4 diagram stubs. Plan first and wait for my approval.
Also build scope items: 30, 31, 42, 43, 44 (docs/BUILD_SCOPE.md).
Follow CLAUDE.md rules: plan first, tests first, make check green, reviewer subagents, add one progress entry in docs/progress/entries/ (from TEMPLATE.md) and update your module file in docs/progress/modules/, run make progress (never edit PROGRESS.md by hand), commit.
Done when: make install && make check green; progress entry added and PROGRESS.md regenerated (make progress); commit phase-0.
```
