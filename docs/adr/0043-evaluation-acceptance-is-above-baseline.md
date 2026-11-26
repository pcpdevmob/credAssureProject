# ADR 0043 — Evaluation acceptance is "above the best single-prompt baseline"; the 92/100 total target is withdrawn

Status: Accepted (owner decision 2026-11-26) · Date: 2026-11-26 · Amends BRD OBJ-07 and §13 (total row) · Relates to
ADR 0042, ADR 0036

## Context
BRD §13 set two acceptance tests for the frozen 100-item test set: a total of at least 92 and a score above the best
single-prompt baseline. The total of 92 was a team-chosen figure, not a course requirement; the course asks for a
measured comparison against a baseline with the effect of each design choice isolated (OBJ-07). The final run (G4, K3,
24 Nov) scored 88/100 against 23/100 for the best baseline (S2). Every category except regulatory answers is at its
category target; regulatory answers are 13/25 against a category target of 20.

## Decision
1. The acceptance test for the full system is: above the best single-prompt baseline on the same model and the same
   frozen items. The total target of 92 is withdrawn from the BRD, the evaluation report generator, the scorecard API
   and page, and the documents.
2. The per-category targets in BRD §13 stay, and are still reported. The regulatory category (13/25 against 20) is
   reported as not met, with the reasons in the G4 report and system card §13.
3. The frozen test set, its gold answers and the scores are unchanged. Nothing is re-run or re-scored for this decision.

## Consequences
- The headline is 88/100 against 23/100 for the best baseline (+65), and it passes the acceptance test.
- The decision was taken after the result was known; this ADR records that, so the change is not read as the score
  meeting a target it was built for. The regulatory gap remains the main limitation.
- Reports dated before 26 Nov keep their dates; their target column now shows the baseline test only.
