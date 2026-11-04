# 09 · Phase 4 — calculation engines

| When | Owner | Prerequisites | Humans must |
|---|---|---|---|
| W2 D1–3 | WC owner + LendWise owner (Pritish) | 05 done (gold exists) | — (APR convention settled by ADR 0012; the test proves it) |

## Paste into Claude Code

```markdown
Run Phase 4 (or /phase 4) in packages/engines, including engines/calendar.py with ADR 0011 for repayment-date → week mapping,
and the CGTMSE basis 'guaranteed amount in year 1, then outstanding'. Add test_apr_rbi_annex_b.py reproducing the RBI KFS Annex B
worked example to 0.01 pp under APR_CONVENTION=nominal (ADR 0012); if it fails, stop and report both conventions.
Also build scope items: 7 (docs/BUILD_SCOPE.md).
Follow CLAUDE.md rules: plan first, tests first, make check green, reviewer subagents, update PROGRESS.md, commit.
When done, run the evaluation(s): E3 (.claude/commands/eval.md) and fix every MUST finding.
Done when: 15/15 cash-flow, 15/15 offers; money-auditor PASS; commit phase-4.
```
