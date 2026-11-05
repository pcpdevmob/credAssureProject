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
| Corpus | done (manual pending) | KR-01, KR-04, G2; ADR 0019 | data: Indian real corpus | 16 Indian sources, target 750. Harvest, download, import, verify, manual, report targets. 233 real available |
| UI U0–U6 | todo | UI-01..09 | | React lane |

## Phase 2 note
- **Plants:** all at or above the DATA_SPEC minimums (PLANTS.md). An independent recompute in `data/generators/tests` checks every case's need, plus an LW-09 cash overlay of every offer.
- **Reviews:** money-auditor found one MUST: eligible offers were sized at the exact need, so they were unaffordable. Fixed: principal is now need + 10%, rounded up to ₹1 lakh. brd-conformance passed with M1 below.
- **Corpus:** 69 manifest entries. A real download (2026-11-05) extracted 51. The lock file is `data/corpus/manifest.lock.json`; raw files and text are gitignored.

## Corpus status (`make corpus-status`, 2026-11-05, after the scripted buffer)
```
Real available 267/500 [##########################........................] 233 to go
Pending 532 | rejected (no text) 223 | needs date or review 20

src tgt+buf avail  pend  rej nodate  name
  1   120+0     6   114    0      0  RBI Master Directions (2025 consolidation)
  2    60+0     2    58    0      0  RBI circulars superseded by the 2025 consolida
  3    60+0     7    52    0      1  RBI FAQs, lending-rate releases (24 months), M
  4  180+20   146    21  219     13  CGTMSE circulars, scheme guidelines, fee pages
  5    25+0     0    25    0      0  NCGTC schemes (ECLGS, CGFMU, CGSSI) guidelines
  6    15+0     0    15    0      0  MUDRA / PMMY circulars and FAQs
  7    40+0     1    38    0      1  Ministry of MSME annual reports and scheme gui
  8    40+0     4    36    0      0  Gazette notifications (MSME classification, GS
  9   30+70    46    53    2      0  CBIC GST circulars and FAQs on financial servi
 10    10+0     0    10    0      0  CBDT on s.43B(h) and Income-tax Act 2025 s.37(
 11   20+20    14     3    0      3  SIDBI publications and MSME Pulse reports
 12    15+0     7     6    0      2  TReDS - RBI directions and platform FAQs/ruleb
 13   40+40    34     6    2      0  Bank and NBFC schedules of charges and sample 
 14    50+0     0    50    0      0  Lok Sabha / Rajya Sabha answers on MSME credit
 15    25+0     0    25    0      0  Supreme Court and High Court judgments on the 
 16    20+0     0    20    0      0  State MSME/industrial policies - Maharashtra (

owner      assigned imported pending
[Name 1]         92        0      92
[Name 2]         87        0      87
[Name 3]         86        0      86
[Name 4]         90        0      90
[Name 5]         85        0      85
[Name 6]         92        0      92
```
- A document counts as available only if it has extracted text **and** an effective date.
  - **Dates by source:** extracted 181, w.e.f. 8, URL 25, PDF metadata 24, retrieved 4 (bank charges only).
  - **Not counted:** 19 need a date and 1 needs review (R-CG-C-001: 2030 is a scheme end date).
  - **Human check:** 27 dates sampled, 10% per source; see `data/corpus/DATE_REVIEW.md`.
- **Scripted buffer (2026-11-05):** targets were raised by a per-source `buffer` (CGTMSE +20, CBIC/GST +70, SIDBI +20, banks +40), giving +44 available.
  - **CBIC/GST Council:** 19 → 46.
  - **CGTMSE:** 130 → 146. 41 more old circulars were scans, so they were rejected and given replacement slots.
  - **Not reachable in plain HTML:** SIDBI MSME Pulse and other lenders' charge pages, so 11 and 13 barely moved.
  - **cbic-gst.gov.in:** timed out mid-run. Its one retry is due after 2026-11-06 08:44 UTC.
- The 520 manual items are split across six owners in `data/corpus/MANUAL_DOWNLOADS.md`. Each section starts with tier 1.
- **One-time retries are due on or after:**
  - 2026-11-06 05:11 UTC: NCGTC (502), MUDRA (connection error), sbi.co.in (timeout);
  - 2026-11-06 08:44 UTC: cbic-gst.gov.in (timeout).

  Run `make corpus-harvest` and `make corpus-download` after both; each outcome is recorded in the lock.
- msme.gov.in (403), Udyam (redirect loop) and RXIL (444) stay manual.
- The commit titled "data: Indian real corpus ≥500" is reserved for when real available reaches 500 or more.

## Open questions (owner, date)
- **Corpus (ADR 0019, 2026-11-05): 267 real Indian documents available, 233 short of 500.**
  - The remaining 517 items are manual: RBI, e-Gazette, incometaxindia, India Code, sansad.in, judgments, state policies, and blocked hosts.
  - They are split across six owners in `data/corpus/MANUAL_DOWNLOADS.md`.
  - The owners save the files, fill the PENDING slots in `manifest.yaml`, and run `make corpus-import`.
  - Deadline: before the G1 corpus freeze. G2 (≥500 indexed) is the hard stop.
  - **Closed (owner):** the 16 RBI documents fetched by script are kept (`fetched_by: script_pre_adr0019`).
  - **Dates:** 242 dated by the chain; 19 need a date and 1 needs review.
  - 181 PDFs, mostly older CGTMSE circulars, are scans with no text layer (no OCR), so they were rejected and given replacement slots.
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
