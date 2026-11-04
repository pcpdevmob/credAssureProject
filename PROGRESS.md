# CredAssure — Progress (Claude Code reads this first and updates it last)

## Current phase
Phase 0b — done (2026-11-05). Next: Phase 1, which needs a go. After Phase 1, approve freezing `AgentResult` (including `agent_version`) and the `tenant_id` decision before anything is frozen at G1.

## Gates
- [ ] G1 (end Week 1): test set + 40 retrieval queries frozen; synthetic data v1; baseline S1–S3; AgentResult frozen; endpoint limits confirmed
- [ ] Skeleton (end Week 1, ADR 0003): placeholder agents end to end through API + reference UI; LLM_ENABLED=false works
- [ ] G2 (end Week 2): ≥500 docs indexed; retrieval report; engines + normaliser green; Onboarding + WC agents end to end
- [ ] G3 (end Week 3): real case end to end with traces; Critic blocks planted bad claims
- [ ] G4 (end Week 4): full eval + ablations; red-team log; Docker; report; demo rehearsed

## Phase log
| Phase | Status | Requirement IDs | Commit | Notes |
|---|---|---|---|---|
| Kit gaps | done | — | phase-0 | R-ID crosswalk, S18–S24, D3/D5/D6 plants, 53-doc manifest, ADR index, ADR 0016 |
| 0 Scaffold | done | NFR-07, NFR-09, APR-03 (config) | phase-0 | 29 tests; make check + make audit green; security-reviewer and brd-conformance MUST findings fixed |
| 0b Monorepo | done | ADR-0005; #46 ports skeleton; #53 import-linter | phase-0b | 52 tests; make check green. security-reviewer and brd-conformance: no MUST. #27, breaking-diff half of #28, and #29 stay later phases |
| UI U0–U6 | todo | UI-01..09 | | React lane |

## Open questions (owner, date)
- Course endpoint context window, JSON/guided-decoding support, token quota (confirm day 2). Local Ollama is settled: `llama3.1:8b`, context 8192, guided JSON off until Phase 6 probes it (ADR 0017).
- Owner names for [Name 1]…[Name 6] and UI lead; replace `@credassure-owner-*` placeholders in `.github/CODEOWNERS`
- Before G1 (from the 5 Nov web check, docs/DATA_RESOURCES.md "Verification status"):
  - GST heading 9971 rate after Notification 15/2025-CT(R) — confirm 18% on loan fees (D7)
  - CGTMSE guarantee ceiling ₹10 cr (RESOURCES D3) vs ₹5 cr on SIDBI page — confirm on cgtmse.in
  - S21 APR fixture needs a second independent transcription from the RBI Annex B PDF (draft at `evaluation/gold/fixtures/`)
  - Bank of Baroda MSME fee table — confirm on the bank's own page
- Phase 7: chromadb 1.5.9 has 5 unfixed advisories (HTTP server mode). Removed from Phase 0 deps; Phase 7 must use embedded
  `PersistentClient` only and record the pip-audit exception or an alternative in an ADR (see ADR 0001).
- `.claude/hooks/guard_paths.py` blocks root `.env.test.example` / `.env.demo.example` listed in REPO_STRUCTURE; profile
  templates live in `deploy/env/` instead. Update REPO_STRUCTURE in Phase 0b or relax the hook.
- `.claude/hooks/*.py` have uncommitted ruff line-wrap changes (no behaviour change) from the first format run; keep or
  restore by hand (`git restore` is blocked by the bash guard).
- `docs/source/170MD.pdf` is an untracked third-party RBI PDF; not committed (BRD §10, L4). Delete or gitignore it.
- `make up` is wired (gateway, web, Ollama, Langfuse; no Chroma server, ADR 0001). It was not started: `deploy/env/langfuse.env` is absent. `docker compose config` for the dev+langfuse profiles lists those services.
- BRD NFR-09 text should be amended to match ADR 0016 in the next BRD revision.

## Settled defaults (ADRs 0012–0017)
- APR nominal, proven by RBI Annex B reproduction (17.07% on exact EMI ₹969.73; rounded ₹970 gives 17.10% and fails)
- Reranker none unless mentor approves · Judge J1 calibrated, kappa ≥ 0.7 else human scoring · Live demo with replay + video fallback · Boundary rule hold
- Langfuse self-hosted in Compose (ADR 0016, approved by owner 2026-11-05)
- Local dev and demo model: Ollama `llama3.1:8b` plus `nomic-embed-text`, context 8192 (ADR 0017). Graded eval stays on the course endpoint.

## Decisions pending (human)
- Add agent_version to AgentResult before G1 (scope #25) — needs ADR 0018 or later (0017 is the Ollama decision). The placeholder field is already on AgentResult and is not frozen
- tenant_id on case tables (scope #27, phase 5) — `TENANT_ID` setting, log field, and an unfrozen AgentResult field already exist. No case tables yet
- Permitted cut order if Week 3 slips (each needs an ADR): scope #35, #41, #38, #37

## Decisions
- See docs/adr/README.md
- LLM_BASE_URL is required outside test mode only when LLM_ENABLED=true (template-fallback and demo-replay runs need no endpoint)

## Scope items done (docs/BUILD_SCOPE.md)
- #30 Config + feature flags (settings.py, README flag table)
- #31 Structured logging (packages/observability log.py, request_id middleware, PII masking incl. uvicorn loggers)
- #42 Ownership and review (CODEOWNERS with placeholders, PR template, CONTRIBUTING.md)
- #43 Architecture records (C4 in ARCHITECTURE.md, ADR index, ADR 0002 STRIDE + OWASP LLM Top 10 register)
- #44 Environment profiles (deploy/compose dev/test/demo/langfuse; deploy/env templates)
- #46 Ports skeleton only (`LLMPort`, `ToolPort`, `LedgerPort`, `RetrievalPort`, `ClockPort` in packages/core). Adapters stay with the agent phases
- #53 Import-linter slice (five contracts in `make check` / CI, plus the web `fetch` pytest). Eval E18 stays in phases 10 and 12
