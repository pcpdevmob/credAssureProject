# How to run the evaluation

TODO owner: Tejas.

## Commands
## Reports

## Phase 11 / P7 (plan v3.4)
```
make eval                                   # 100 items through the API on the configured model -> var/eval/<run>/
make eval-ablations                         # A1-A5, each on its affected categories (ablations.yaml)
make eval-judge RUN=var/eval/<run>          # J1 grades regulatory answers; writes a blind 20% human sample CSV
make eval-kappa RUN=var/eval/<run>          # after labelling: kappa >= 0.7 -> J1 scores free text, else humans
make eval-report RUN=var/eval/<run> ABL="var/eval/<run>-A1 ..." OUT=evaluation/reports/E13-<date>.md
make load-smoke                             # 10 concurrent demo cases, p95 per stage (Q6: funding < 60 s)
make eval ARGS="--fake --only routing"      # mechanics only (FakeLLM); never a score
```
Baseline S1-S3 results (`make baseline`, gitignored under evaluation/baseline/results/) are read by the report for the
"above the best baseline" check. Degradation matrix: `docs/evaluation/degradation-matrix.md`.

