# Evaluation

**Owner:** Abhishek (Phase 11); Tejas (test set)
**Phases:** P1 (close G1), P2 (G3), P6 (course baseline, deferred), P7 (Phase 11), P11 (G4)
**Status:** G1 provisionally frozen 2026-11-15; G2 passed; **G3 passed 2026-11-18** (G3 + E18 READY); G1-final checklist open; **P7 code done 2026-11-18**: make eval harness, J1 + kappa, E13 report, A1-A5 runner, degradation matrix, load smoke (live runs pending on the Mac); **K3 done 2026-11-24** (88/100, A2 38/51); **K4 done 2026-11-25** (J1 vs two human labellers, kappa 0.789; 16/25 regulatory right by content vs 13/25 strict)

## Open items
- G3 carry: re-record one live-model demo run with a Langfuse trace at P4 (needs the Mac).
- E18 SHOULDs: ARCHITECTURE §5.1/§7 say React SPA/nginx (Next.js, ADR 0022); §6.3 omits RETURNED — P10 docs pass.
- G1-final: human judging (249) + weighted kappa ≥ 0.7; hand check (10 rows); APR transcription 17.07%; owner names (HISTORY "G1-final checklist").
- Baseline S1–S3 on qwen3:8b done 2026-11-19 (S1 20, S2 23, S3 22; system 88); course-endpoint baseline not needed (ADR 0036).
- RAG-only baseline: `make rag-baseline` on the Mac (script on `feature/evaluation-p11f`), then fill the G4 four-row table.
- P7 live runs on the Mac: make eval-ablations (A6 with K5), make load-smoke (make eval, eval-judge, eval-kappa, eval-report done for K3/K4).
- K6 red-team (11.12): runner `make redteam` + `docs/redteam_log.md` ready (20 frozen + 5 E14 probes, verdicts by state/leak checks); live run on the Mac, then paste results and fill the Fix column.
