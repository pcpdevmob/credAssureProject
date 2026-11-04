# 04 · Phase 2 — synthetic data and open corpus

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W1 D2–4 | Copilot owner (corpus) + WC/LendWise owners (generators) | 03 done | Open every *verify* URL in docs/DATA_RESOURCES.md; spot-check PLANTS.md |

## Paste into Claude Code

```markdown
Run Phase 2 (or /phase 2). Generators for S01–S17 cite public source IDs (P-xx) in their headers. Build data/corpus/manifest.yaml
from docs/DATA_RESOURCES.md with legal_basis on every entry, the throttled downloader, text extraction and data/corpus/audit.py.
Also build scope items: 14 (docs/BUILD_SCOPE.md).
Follow CLAUDE.md rules: plan first, tests first, make check green, reviewer subagents, update PROGRESS.md, commit.
When done, run the evaluation(s): E1, E2 (.claude/commands/eval.md) and fix every MUST finding.
Done when: make data byte-identical twice; ≥400 real documents; audit passes; commit phase-2.
```
