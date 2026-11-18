# AI Security and Guardrails

**Owner:** Pritish (GR); Abhishek (red-team, SEC)
**Phases:** P2 (pattern tests), P3 (GR), P8 (SEC), P10 (threat model)
**Status:** Phase 6 safeguards done (PII masking, injection scanner, breaker, caps); consolidation into packages/guardrails pending (P3)

## Open items
- Injection pattern tests: plan-then-execute, map-reduce isolation, context-minimisation (P2).
- packages/guardrails, rails R1–R5, guardrail_event, policy YAML; Presidio behind the money-preservation gate (P3).
- safety_v2 suite (40) frozen before first run; OWASP LLM + ASI tests; A6 (P8).
- Fuzz fixture has no case and no VP run (HISTORY "Phase 10b notes", Open).
- chromadb 1.5.9 advisories accepted, embedded mode only (ADR 0024).
