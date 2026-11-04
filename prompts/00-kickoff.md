# 00 · Kick-off: load context, find conflicts

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W1 D1 | Integration lead | Kit unzipped in an empty git repo; Claude Code started at repo root | Answer Claude's conflict list; confirm endpoint details are in .env (Claude cannot read it) |

## Paste into Claude Code

```markdown
Read CLAUDE.md, START_HERE.md, PROGRESS.md and every file CLAUDE.md imports, plus docs/REPO_STRUCTURE.md, docs/BUILD_SCOPE.md,
docs/DATA_RESOURCES.md, CLAUDE_CODE_MASTER_PROMPT.md, CLAUDE_CODE_REPO_PROMPT.md and CLAUDE_CODE_UI_PROMPT.md. Write no code. Reply with:
1. One paragraph: what we build and the non-negotiables.
2. The ordered list of prompt files in prompts/ you expect to run, with the gate each feeds.
3. Every conflict or ambiguity across BRD, ADRs, architecture, data docs and BUILD_SCOPE, each with a proposed resolution.
4. What you need from humans before prompt 01.
Follow CLAUDE.md rules: plan first, tests first, make check green, reviewer subagents, update PROGRESS.md, commit.
Done when: Conflicts resolved in PROGRESS.md 'Decisions'.
```
