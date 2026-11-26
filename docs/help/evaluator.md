# Evaluator

The evaluator checks that the system did what it says: every event recorded, every guardrail decision visible, and
the test-set score measured. You can read every case but cannot change one.

## Audit
Open a case and choose **Audit**. The list shows every stage, fact, gate, guardrail event and decision with its time
and actor. The badge at the top says **Hash chain verified** when every event still links to the one before it. If it
ever says **Hash chain broken**, an event was changed or removed: report it at once. **Audit log** in the menu lists
events across all cases.

## Safety events
**Review & approval** on a case shows the **Safety checks on this case** panel: counts and codes of what the guardrails and the
Verification Critic blocked, redacted or flagged. The panel never shows the blocked text itself.

## Eval runs
**Evaluation** shows the frozen 100-item test set scored three ways: the best single-prompt baseline (S1–S3), the full
system, and each ablation (A1–A6) on the categories it affects. The full system passes when it scores above the best
baseline. An ablation effect counts only when it shows in more than one category or again on a rerun.

Runs start from the command line, not from this page: `make eval`, then `make eval-judge`, `make eval-kappa` and
`make eval-report`. The page reads the newest run of each kind. Until a run exists it says so. Full steps:
`docs/evaluation/how-to-run.md`.
