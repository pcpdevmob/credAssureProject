# CredAssure — Progress (Claude Code reads this first and updates it last)

## Current phase
Phase 2 is done (2026-11-05). Next is Phase 3: eval set, independent gold and baseline. Two things are still open:
- **ADR 0018 freeze (human):** ADR 0018 (AgentResult, including `agent_version` and `tenant_id`) is Proposed and not frozen. Accept it before G1.
- **Corpus shortfall (M1):** the corpus is short of the ≥400 real-document target. See open questions.

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
| 1 Contract | done | VER-01, BR-05; #8 #9 #21 schema #24 #25 field #26 #32 #46 ADR | phase-1 | 149 tests. Money auditor and security reviewer: no MUST. BRD: the Phase 0b retry route stays HTTP 501; the retry behaviour is Phase 9. ADR 0018 Proposed. E4 critic half waits for Phase 9d |
| 1 gap fix | done | VER-01, BRD §10 | phase-1-fix | Normaliser `find_all` (free-text scan with spans, `kind`), signed money/rates; RBI PDF untracked; REPO_STRUCTURE env templates point to deploy/env |
| 2 Data | done | BR-01, BR-14, BRD §10, scope #14; S01–S06, S18–S20, S22 | phase-2 | 393 files in `data/frozen/v1`, byte-identical (SHA256SUMS + test). See note below |
| UI U0–U6 | todo | UI-01..09 | | React lane |

## Phase 2 note
- **Plants:** all at or above the DATA_SPEC minimums (PLANTS.md). An independent recompute in `data/generators/tests` checks every case's need, plus an LW-09 cash overlay of every offer.
- **Reviews:** money-auditor found one MUST: eligible offers were sized at the exact need, so they were unaffordable. Fixed: principal is now need + 10%, rounded up to ₹1 lakh. brd-conformance passed with M1 below.
- **Corpus:** 69 manifest entries. A real download (2026-11-05) extracted 51. The lock file is `data/corpus/manifest.lock.json`; raw files and text are gitignored.

## Open questions (owner, date)
- **M1 corpus shortfall (Copilot owner [Name 6]):** the deadline is the G1 corpus freeze; G2 (≥500 indexed) is the hard stop.
  - Targets are ≥400 real documents (prompts/04), 320–380 public (DATA_SPEC §6) and ≥500 indexed at G2. The manifest has 69 public entries; 51 downloaded.
  - Even if all 69 download, the total is 69 + 135 KFS + 62 policies = 266.
  - The cheapest way to grow is the `rbi_circulars_hist` and `cgtmse` collections (RESOURCES §6).
  - The 18 entries that failed need a URL fix: 4 "pdf" URLs serve HTML, plus 403 errors, timeouts and robots blocks (see the lock file).
- **Conventions Phase 3 gold and Phase 4 engines must match:** these are written in the generator headers, `cases.py` and `offers.py`.
  - Receivables count in their expected week.
  - Mitigations are never inflows.
  - Moratorium interest is serviced monthly.
  - Charge timing: annual charges fall at months 0, 12, …; CGTMSE is paid in year 1 at disbursal.
  - Eligible = no missing term, no mismatch, not unaffordable, not late or short.
  - Confirm them, or write an ADR.
- **Phase 3 must confirm every offer tag in PLANTS.md against independent gold before the FROZEN marker (S6).**
- **`data/frozen/v1/_design/designs.json` is design intent.** Gold must not read it; add a Phase 3 test for that.
- **Not yet assigned to a phase:** S07 negotiation templates, S09 chat-intent examples (~60), S11 banned phrases, S13 report templates.
- Course endpoint context window, JSON/guided-decoding support, token quota (confirm day 2). Local Ollama is settled: `llama3.1:8b`, context 8192, guided JSON off until Phase 6 probes it (ADR 0017).
- Owner names for [Name 1]…[Name 6] and UI lead; replace `@credassure-owner-*` placeholders in `.github/CODEOWNERS`
- Before G1 (from the 5 Nov web check, docs/DATA_RESOURCES.md "Verification status"):
  - GST heading 9971 rate after Notification 15/2025-CT(R) — confirm 18% on loan fees (D7)
  - CGTMSE guarantee ceiling ₹10 cr (RESOURCES D3) vs ₹5 cr on SIDBI page — confirm on cgtmse.in
  - S21 APR fixture needs a second independent transcription from the RBI Annex B PDF (draft at `evaluation/gold/fixtures/`)
  - Bank of Baroda MSME fee table — confirm on the bank's own page
- Phase 7: chromadb 1.5.9 has 5 unfixed advisories (HTTP server mode). Removed from Phase 0 deps; Phase 7 must use embedded
  `PersistentClient` only and record the pip-audit exception or an alternative in an ADR (see ADR 0001).
- `docs/source/170MD.pdf` (third-party RBI PDF) was tracked; untracked and `docs/**/*.pdf` gitignored on 2026-11-05
  (BRD §10, L4). It stays in history from phase-0b, because we never rewrite history. Delete the local copy if not needed.
- `make up` is wired (gateway, web, Ollama, Langfuse; no Chroma server, ADR 0001). It was not started: `deploy/env/langfuse.env` is absent. `docker compose config` for the dev+langfuse profiles lists those services.
- BRD NFR-09 text should be amended to match ADR 0016 in the next BRD revision.

## Settled defaults (ADRs 0012–0017)
- APR nominal, proven by RBI Annex B reproduction (17.07% on exact EMI ₹969.73; rounded ₹970 gives 17.10% and fails)
- Reranker none unless mentor approves · Judge J1 calibrated, kappa ≥ 0.7 else human scoring · Live demo with replay + video fallback · Boundary rule hold
- Langfuse self-hosted in Compose (ADR 0016, approved by owner 2026-11-05)
- Local dev and demo model: Ollama `llama3.1:8b` plus `nomic-embed-text`, context 8192 (ADR 0017). Graded eval stays on the course endpoint.

## Decisions pending (human)
- Accept ADR 0018 before G1 to freeze AgentResult, including `agent_version` (scope #25). The field is on the model. The stage-retry route stays in Phase 9
- tenant_id on case tables (scope #27, phase 5) — `TENANT_ID` setting, log field, and an unfrozen AgentResult field already exist. No case tables yet. ADR 0018 does not decide this
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
- #46 Ports skeleton only (`LLMPort`, `ToolPort`, `LedgerPort`, `RetrievalPort`, `ClockPort` in packages/core). ADR 0006 accepted. Adapters stay with Phase 8
- #53 Import-linter slice (five contracts in `make check` / CI, plus the web `fetch` pytest). Eval E18 stays in phases 10 and 12
- #8 Rounding policy (ADR 0010; `packages/core` money helpers)
- #9 Blocker catalogue (`BlockerCode`, gate vs warning vs needs-input)
- #21 CriticFinding schema only. Regeneration stays in Phase 9d
- #24 Agent registry and data-access matrix (`agents/registry.yaml`, `packages/tools` authorize)
- #25 `agent_version` field on AgentResult. Retry route stays in Phase 9. Freeze is ADR 0018, still Proposed
- #26 Excluded multi-agent patterns (ADR 0009)
- #14 Corpus legal-basis audit (`make corpus-audit`, `credassure.datagen.corpus`; throttled downloader `make corpus-download`)
- #32 Error catalogue (`ApiErrorCode`). HTTP behaviour of the 501 routes is unchanged
