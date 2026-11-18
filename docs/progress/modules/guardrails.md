# AI Security and Guardrails

**Owner:** Pritish (GR); Abhishek (red-team, SEC)
**Phases:** P2 (pattern tests), P3 (GR), P8 (SEC), P10 (threat model)
**Status:** Phase 6 safeguards done (PII masking, injection scanner, breaker, caps); ADR 0033 pattern tests in make check (P2); **P3 done 2026-11-18**: packages/guardrails (R1–R5, guardrail_event, config/guardrails.yaml), PII v2 (Presidio patterns + GSTIN/UPI/card/Udyam), money gate, trace-leak test 0 hits, data classes, CSV escaping, gen_ai.* export

## Open items
- Employee names are not yet matched against hr.db (ADR 0030 §2) — P8.
- E4 was re-run as its test suites in the cloud (no corpus); the full /eval E4 with the 12 citation plants runs on the Mac at P4.
- safety_v2 suite (40) frozen before first run; OWASP LLM + ASI tests; A6 (P8).
- Fuzz fixture has no case and no VP run (HISTORY "Phase 10b notes", Open).
- chromadb 1.5.9 advisories accepted, embedded mode only (ADR 0024).
