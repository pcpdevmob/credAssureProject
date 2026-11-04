# 02 · Phase 0b — monorepo scaffold (ADR 0005)

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W1 D1–2 | Integration lead | 01 done | Approve the move plan |

## Paste into Claude Code

```markdown
Run the prompt inside CLAUDE_CODE_REPO_PROMPT.md (or /scaffold-repo). Also move docs/source/, docs/BRD.md and the other flat docs
into the docs/<section>/ layout with stubs at the old paths, and copy prompts/ unchanged.
Also build scope items: 27, 28, 29, 46 (ports skeleton), 53 (import-linter) (docs/BUILD_SCOPE.md).
Follow CLAUDE.md rules: plan first, tests first, make check green, reviewer subagents, update PROGRESS.md, commit.
Done when: make check, import-linter, make openapi && make client, make up all succeed; commit phase-0b.
```
