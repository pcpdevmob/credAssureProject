# ADR 0014 — Automated judge
Status: Accepted · 2026-11-04
Decision: free-text items are scored by the course model with prompt J1 and calibrated against human labels on 20% of them.
If Cohen's kappa < 0.7, all free-text items are scored by two humans (disagreements resolved by a third) and the judge is reported as unreliable.
