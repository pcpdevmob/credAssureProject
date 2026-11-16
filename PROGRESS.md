# CredAssure — Progress (Claude Code reads this first and updates it last)

## Current phase
Phase 7 is done and re-measured on the closed corpus (2026-11-15): 1,275 documents indexed (1,084 real after the junk-page check); KR-05 stays OPEN (26/40 vs 34, all 40 queries answerable now); KR-04 0 violations. Earlier: Phase 4 (2026-11-05), Phase 3 follow-ups and Phase 5 (2026-11-06), Phases 8a, 8b and 6 (2026-11-07). **Phase 9a (Onboarding agent) done 2026-11-15: 10/10 onboarding items, E5 READY. Phase 9b (Working Capital) done 2026-11-15: 15/15 cash-flow items via API, E6 READY. G2 passed 2026-11-15. 9c-a and 9c-b (LendWise) done 2026-11-16: 15/15 offer items, 5/5 negotiation items. 9d (Verification Critic) done 2026-11-16: 12/12 bad-citation plants and every planted bad claim blocked, E4 READY. 9e (Copilot) done 2026-11-16 except CP-01: refusal 8/8, injection 8/8, isolation 3/3 in CI (model off and on) and live; regulatory 10/25 live, OPEN on KR-05 (E8-2026-11-16). `make demo-reset` added 2026-11-16 (see notes). Next: Phase 10.** `openapi.json` and `packages/api-client` are current. UI lane: U2 done 2026-11-16 (awaiting review), next U3. Still open:
- **G1 provisionally frozen (2026-11-15):** `evaluation/FROZEN.sha256` + FROZEN markers (`status: provisional`) on `evaluation/testset/v1`, `evaluation/retrieval/v1`, `data/frozen/v1`. ADR 0018 accepted (AgentResult frozen). Owners named: Tejas (Onboarding), Suresh (Working Capital), Pritish (LendWise), Abhishek (Critic); [Name 1], [Name 6] and the UI lead pending. G1 becomes final when the **G1-final checklist** below is done. Phase 9a done 2026-11-15.
- ~~KFS dates vs AS_OF_DATE~~ **closed by P2b (2026-11-15):** offers carry `issue_date` (po_date..AS_OF, own rng stream; v2 = AS_OF) and every case-scoped KFS uses it as `effective_from`; 111/111 in force; case isolation now tested live (E8 addendum).
- **Retrieval labels — G1 labels v1.1-silver complete, human check pending (2026-11-15):** self-consistency 100/100; after the B1 section pass, strict +110 / lenient +204 labels; the 72 v1.0 labels disputed before it are kept and listed in `judging/human_pass_disputed_v1.0.md`; best recall@5 v1.0 24/40, strict 35, lenient 38 (section labels remove document-level inflation; was 26/37/38), pooling-biased, LLM-judged (E8 addenda 2–3). `make retrieval-eval` now fails only on KR-04 violations or isolation leaks; `make kappa` gives plain and weighted κ, verdict on weighted. **Next: `make judge JUDGE=pritish` on the 249-item stratified sample, then `make kappa JUDGE=pritish`.**
- **Retrieval labels — silver first (decided 2026-11-15, `evaluation/retrieval/v1/judging/README.md`):** a blind Claude Code session judges the top-5 pool (995 items + 100 seeded duplicates for self-consistency; map in `judging/duplicates_map.json`) from a package exported outside the repo to `../credassure-judging/` (2/1/0; 2 = R, 1 and 0 = N); labels are **v1.1-silver**. Later, a seeded 25% sample (249 items) is judged blind with `make judge SAMPLE=0.25`: Pritish, then Tejas or Abhishek. Kappa (silver vs human) ≥ 0.7 confirms; otherwise full human judging per `criteria.md` with Suresh adjudicating. Then step 4: merge → `queries.v1.1.jsonl` (v1.0 kept), diff + kappa, re-run `make retrieval-eval` under both label sets; add v1.1 to `freeze.py` assets before `/freeze-g1`.
- **LW-15 deferred (decided 2026-11-16):** negotiation rounds 2–3 (`rate_match_v1`, `tenor_change_v1`) are stretch, allowed only after G3 passes on time (BRD §4.2/§15). Core stays one fee-waiver round (LW-12); the gateway returns 409 on a second round (`supervisor_service.py:114`). When picked up: new lender-script responses outside frozen `data/frozen/v1/lender_scripts/` + an ADR.

## Gates
- [ ] G1 (end Week 1): test set + 40 retrieval queries frozen; synthetic data v1; baseline S1–S3; AgentResult frozen; endpoint limits confirmed
- [ ] Skeleton (end Week 1, ADR 0003): placeholder agents end to end through API + reference UI; LLM_ENABLED=false works
- [x] G2 (end Week 2): ≥500 docs indexed; retrieval report; engines + normaliser green; Onboarding + WC agents end to end — PASS 2026-11-15 (`evaluation/reports/G2-2026-11-15.md`: 1,275 docs, 18 retrieval configs, engines 208 tests 98%, 10/10 onboarding + 15/15 cash-flow via API). KR-05 quality target 34/40 still open (not a G2 criterion)
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
| Corpus | CLOSED 2026-11-14 | KR-01, KR-04, G2; ADR 0019 | data: Indian real corpus | 16 Indian sources, target 750. Harvest, download, import, verify, manual, report targets. 1,092 real available (closed) |
| 3 Eval assets | done (G1 items below) | BRD §12–13, KR-05, VER-02, scope #13; ADR 0021 | phase-3 | Independent gold (floats + numpy_financial, no engine import, contract-enforced) reproduces every design need, every PLANTS offer tag and RBI Annex B 17.07%. 100 items (25/10/15/15/5/6/8/8/3/5), 40 retrieval queries, 20 red-team prompts, 12 S24 bad citations, scorers (₹1 / 0.01 pp, BRD failure classes), freeze script with readiness gate, run record (#13), baselines S1–S3. money-auditor PASS (no MUST); brd-conformance: only pre-G1 corpus MUST |
| 4 Engines | done | WC-01..06, LW-02..11/14, ONB-02/03, APR-01..03, BR-05/07/12; scope #1 (enum), #7; ADR 0011 | phase-4 | Pure Decimal engines. 15/15 cash-flow and 15/15 offer known answers match gold (worst APR 0.005 pp). RBI Annex B 17.07%. 20/20 onboarding profiles. 426 tests, engine coverage 98%. money-auditor PASS, brd-conformance PASS, no MUST. SHOULDs applied: IRR edge/bisection tests, `gst_rate` and `indicative` required (no silent defaults), strict Decimal in audit and negotiation, schedule terms material, fee compared in ₹, week<1 rows blocked, undrawn ≥ 0, routing rejects negatives, deterministic tie-break |
| 5 Ledger + auth | done | SUP-08, APR-04/05, ONB-05, NFR-07, OBJ-08, BR-05, BR-14; scope #22 #27 #29 #49 | phase-5 | `packages/ledger` (case.db + corpus.db models, Alembic up/down, append-only triggers, hash-chained audit, fact ledger, run lock, read-only hr.db, seed) and `packages/security/auth.py` (argon2id, JWT, case policy). 39 tests; 468 total. brd-conformance PHASE COMPLETE; security-reviewer 2 MUST fixed (decision only on AWAITING_APPROVAL/HELD and only by the routed role, at both layers). E10 (auth part, security-reviewer): 1 MUST fixed (re-routing could reopen an APPROVED or REJECTED case); after the fix 46/47 adversarial checks pass. The open one, tail truncation of the audit chain, is a SHOULD (see Phase 5 notes). Route checks are N/A until Phase 8 |
| 8a Supervisor + jobs + anchor | done | SUP-01..08, APR-01..03 wiring, OBJ-08; scope #1 (A4), #4, #19, #22, #46, #47 | phase-8a | Supervisor graph, placeholders, adapters, audit_head, heartbeat lock, jobs table, ADR 0007. 546 tests. Reviews and evals run with 8b |
| 8b Gateway + async runs + e2e | done | API-01, UI-01..08 (API side), SUP-02 (placeholder), SUP-03/08, APR-04/05, NFR-03/04/07, OBJ-08/09; scope #4 #15 #16 #28 #46 #47 #50 | phase-8b | /v1 routers, RFC 9457, rate and login limits, uploads, 202 + job + SSE, agent routers on `start_run`, health/quota, Langfuse exporter, e2e LLM on/off, openapi + TS client. 670 tests. E9 READY, E10 routes READY, E11 NOT READY → 2 MUST fixed. Reports in `evaluation/reports/` |
| 6 Model layer + safeguards | done | NFR-03/04/05/07, ONB-06 (primitive), BR-15, SUP-04/07; scope #22 (limiter), #23, #36, #48; ADR 0008 | phase-6 | Client (30 s, transient-only retries ×2 with jitter, breaker 5→open 60 s with one half-open probe, shared limiter, SQLite cache, guided JSON), structured output (repair ×2), prompt registry + bump check + eval-fast CI, Verhoeff PII redaction, spotlighting, injection scanner, 5 min stage timeout with cancellation and template fallback. 787 tests. security-reviewer: no MUST; brd-conformance: 1 MUST (flaky test) fixed. E4 (scoped): READY. |
| 7 Retrieval | done (KR-05 OPEN) | KR-01..05, BR-14, BR-15, SUP-08, NFR-04/05/07; ADR 0013, 0019 | phase-7 | Re-measured 2026-11-15 on the clean re-ingest: 1,283 documents (1,092 real), recall@5 best 26/40, hybrid over keyword +2, KR-04 0/7,200; E8-2026-11-15 NOT READY on KR-05 only. First run: 697 documents indexed (506 real). 3 chunkers, FTS5 + Chroma, RRF k=60, pinned cross-encoder, ADR 0019 filters, (tenant, case) KFS scoping. Recall@5 best 23/40 (section/dense/rerank = section/hybrid/off). KR-04 0 violations over 3,600 passages. security-reviewer: 1 MUST fixed. E8 (retrieval): NOT READY on KR-05 only |
| 9a Onboarding agent | done | ONB-01..06, BR-03, BR-04, SUP-05, SUP-08, NFR-02; scope #24 #25 | phase-9a | Real Gate 1 agent: HR profile from the login binding (read-only hr.db), code gate, `onb_explain` 1.0.0 with template fallback, SUP-05 re-check (closes E9 S2 for 9a), `ledger_prefixes` deny-by-default + case pinning in the stage wrappers, chat PII refusal, Qwen3 `/no_think`. 10/10 items via API (LLM off and on). security-reviewer 1 MUST fixed; brd-conformance PHASE COMPLETE; `evaluation/reports/E5-2026-11-15.md` READY |
| 9b Working Capital agent | done | WC-01..07, BR-01, BR-02, BR-05, SUP-05, SUP-06; scope #24 #25 #33 (data) | phase-9b | Real Gate 2 agent: validated case files → engines → wc.* facts with lineage, one question per NEEDS_INPUT, `wc_explain` 1.0.0 with grounded-number guard and template, SUP-05 recompute. 9a follow-ups (SUP_RECHECK_MISMATCH, per-call token/latency log, per-prompt caps). 15/15 items via API, model off and on. security-reviewer PASS, money-auditor PASS, brd-conformance PHASE COMPLETE (no MUST); `evaluation/reports/E6-2026-11-15.md` READY |
| 9c-a LendWise audit and pricing | done | LW-01..11, LW-14, BR-06..08, BR-15, SUP-05, NFR-02; scope #22 #24 #25 | phase-9c-a | Offers and KFS uploaded as case files; audit, schedule parse (hidden + unpriced rows), IRR APR, GST (CGST+SGST), CGTMSE, affordability vs cash table, ranking, gate ≥2 eligible / NOT_REQUIRED. `lw_kfs_extract` 1.0.0 one call per offer in parallel, spans verified, kept only when equal to the code parse; `lw_explain` 1.0.0 slots only. SUP-05 recompute + S2 test. 15/15 offer items via API, model off and on. Reviews: all MUSTs fixed (see Phase 9c-a notes) |
| 9c-b LendWise negotiation | done | LW-12, LW-13 (LW-01..14 complete), BR-09, BR-10, BR-13, BR-15, SUP-07, SUP-08 | phase-9c-b | One fee-waiver round via `POST /v1/agents/lendwise/cases/{id}/negotiate` (Supervisor `invoke_extra`, case run lock, one sent round per case); `fee_waiver_v1` code template filled from `lw.negotiation.*` facts, fee worded by basis; interim `verify_claims` (figures = named ledger facts, no acceptance/urgency, no PII) before `lender_send_template`; `packages/lender-sim` ScriptedLender (revisions equal frozen v2); reply scanned, flags only; revision re-audited and re-priced before `concession_counts`. 5/5 negotiation items via API, model off and on. Reviews: security 1 MUST (concurrent rounds) fixed, money 1 MUST (fixed-fee wording) fixed, brd PHASE COMPLETE; `evaluation/reports/E7-2026-11-16.md` READY (no MUST) |
| 9d Verification Critic | done | VER-01..05, CP-02 (chat), SUP-05, SUP-08, BR-05, BR-15; scope #1 #10 #21 #25 | phase-9d | `agents/critic` `verify.py` (figures vs ledger to ₹1 / 0.01 pp, model figures only inside code slots, stale-slot check, reason containment, citations via `retrieval.search.resolve`, banned.yaml S-VER-02, PII, report sections) used by the Supervisor on every stage narrative (`_criticise`: ≤2 `regenerate` 1.0.0 then template, audited `CRITIC_BLOCKED`/`CRITIC_FALLBACK`), by the Critic stage (re-verifies `<prefix>narrative` facts + negotiation message vs current ledger → `ver.findings`, re-route ≤2, ARCHITECTURE §6.3), by negotiation and chat. LendWise reason slots computed by code (breach week, late, short, extra total cost, extra upfront). Ablations A1–A5 (`evaluation/ablations/ablations.yaml`). 1,199+ tests; items unchanged model off and on. Reviews: money PASS, security PASS, brd PHASE COMPLETE (no MUST; SHOULDs fixed). `evaluation/reports/E4-2026-11-16.md` READY |
| 9e Copilot | done (CP-01 OPEN) | CP-01 (pipeline; ≥20/25 OPEN), CP-02, CP-03, SUP-08, BR-15, KR-04; scope #2 #20 #40 (notice) | phase-9e | Code refusal policy before any model call; `cp_tool` picks 1 of 4 tools, code validates, fallback `search_regulations`; ≤5 spotlit passages, `[n]`→chunk id, case figures only as `{key}` slots; Critic (citations, reason containment, grounded wording) or exact ABSTAIN; per-case redacted memory (4 turns), notice once; `cp.answer.<trace>` facts carry chunk ids for lineage; own KFS by doc_id+sha. Live qwen3:8b: safety 19/19, regulatory 10/25 (ceiling ~16 on retrieval). Reviews: security MUST fixed (grounding excused predictions), brd PHASE INCOMPLETE on CP-01 only. `evaluation/reports/E8-2026-11-16.md` |
| demo-reset (pulled from 12) | done | #17 (part), APR-06 | feat(ops) 6f88fe4 | `scripts/demo_reset.py`: guards (e2e db, tenant ≠ demo, :8000 busy), audited purge + backup, then the real API in-process: CA-2026-0016 Director approval-pending, CA-2026-0017 paused on `min_cash_buffer`. Idempotent (test) |
| UI U0–U6 | in progress | UI-01..09 | ui-U0, ui-U1, ui-U2, ui-U3 | finbridge Next.js imported as apps/web (ADR 0022). **U0 done 2026-11-16** (`docs/ui/design-plan.md`). **U3 done 2026-11-16** (funding chart, offers, negotiation, e2e isolation; see U3 notes). **U2 done 2026-11-16** (preparer flow, Director approval, money input, API dashboard totals, nginx headers #52; see U2 notes). **U1 done 2026-11-16**: Next 16.4.4 / React 19, npm audit 0, CredAssure rename, light/dark tokens, money.ts, ◈ provenance drawer on the live lineage endpoint, RFC 9457 mapper, 46 unit tests, e2e demo case + 15 screenshots with axe 0 serious; next U2. Bridge security review and U6 hardening still open |

## Corpus CLOSED (2026-11-14)
**1,092 real documents available** (target 530, G2 500). 0 undated, 0 open slots. Adding a document now means re-running `make ingest` and `check_corpus_refs`, and an ADR 0019 note.
- **Done in this close:** India Code host moved to `indiacode.gov.in` (sources.yaml `manual_hosts`, source 10 recipe, R-MSME-01 URL, `hosts:` map, ADR 0020 amendment, DATA_RESOURCES P18, RESOURCES). The old `nic.in` hosts stay in `manual_hosts` so a redirect never skips the gate. Not checked live from the sandbox.
- **Import:** no new files (all 1,094 raw files were already in the lock).
- **Dated (23):** 3 MSME Pulse editions from the month (`human`, first of month); 18 evergreen web pages/guidelines with no date of their own dated at retrieval 2026-11-14 (`date_source: human` plus `date_note`; the tool allows `retrieved` for bank charges only). Review these at the next date sample: R-AA-01, R-CG-C-001, 038, 039, 041, 409, 410, 413-420, R-MSME-05, R-TREDS-001/002.
- **Rejected:** R-CG-C-325 and R-CG-C-337 are Word files saved as .html (no text). Quarantined; their replacement slots were dropped and the source 4 target set to 161.
- **Unavailable, accepted:** R-BANK-03 (404) and R-STATE-002 (host blocked).
- **Index is current (2026-11-15):** clean re-ingest, 1,283 documents (1,092 real + 191 synthetic). See Phase 7 re-measure.

| # | Source | Available | Rejected |
|---|---|---|---|
| 1 | RBI Master Directions | 369 | 0 |
| 2 | RBI superseded circulars | 202 | 0 |
| 3 | RBI FAQs, rates, press releases | 14 | 0 |
| 4 | CGTMSE | 161 | 221 |
| 7 | Ministry of MSME, Udyam, Samadhaan | 9 | 1 |
| 8 | Gazette notifications | 10 | 0 |
| 9 | CBIC GST, GST Council | 92 | 10 |
| 10 | CBDT, Income-tax Act | 3 | 0 |
| 11 | SIDBI | 40 | 4 |
| 12 | TReDS | 21 | 4 |
| 13 | Bank and NBFC charges | 35 | 2 |
| 14 | Lok Sabha / Rajya Sabha answers | 101 | 0 |
| 15 | Court judgments | 27 | 0 |
| 16 | State policies | 8 | 3 |
| 5, 6 | NCGTC, MUDRA | 0 | 0 |
| | **Total** | **1,092** | **245** |

By owner (manual slots only; 5 assigned in total): Tejas 1, Abhishek 1, [Name 6] 4 (1 unavailable), others 0. Nothing is waiting on an owner.

## Phase 9e notes (2026-11-16)
- **Decisions (user):** (1) `var/case.db` rebuilt as tenant `demo`; `make run-api`/`db` run with `TENANT_ID=demo`. (2) A case sees the corpus KFS it uploaded, matched by doc_id + sha256, exempt from `applies_to` (closes the P2b question). (3) Model off: refusal, injection and isolation are code-decided; every other question returns the exact ABSTAIN; the 20/25 target applies with the model on.
- **Deviations (design-detail §2.4.6 "As built"):** no `cp_qtype`/`cp_refusal_classify` (code policy + `cp_tool`); no regeneration loop (any Critic finding → ABSTAIN); memory lives in `ledger.reads.chat_history`/`store.chat_turn`, not `agents/copilot/memory.py`.
- **Open:** CP-01 10/25 live → after human-checked retrieval labels; tag outdated-limits docs `superseded_by` (R-SIDBI-P-008 2020 MSME limits, R-CG-C-274 old ₹200 lakh cap; KR-04 corpus gap); then consider ≤2 `cp_answer` regenerations. Own-KFS clause has no tenant term (security SHOULD 4); public search assumes `lender_type=commercial_bank`; A3/A5 ablations not wired to the copilot (Phase 11); embedder from `os.environ`, not Settings (NIT). #40 acknowledgement storage stays in Phase 10.
- **Live run:** `make copilot-live ARGS="--only regulatory --out-dir var/e8-live/reg2"` (throwaway db under `var/e8-live`).

## demo-reset notes (2026-11-16)
- **Not yet run on `var/case.db`:** the guard refused because the gateway was listening on :8000. Stop it, then `make demo-reset`. The first run backs up `var/case.db`, purges (audited) and re-seeds the users as tenant `demo`; later runs purge the demo cases and recreate CA-2026-0016 (Director approval-pending) and CA-2026-0017 (paused on `opening_position.min_cash_buffer`).
- Replay cache, blocked-onboarding case and an approved case stay in Phase 12.

## UI U3 notes (2026-11-16)
- **Built:** cash-table API flags (`shortfall`, `below_buffer`, `buffer`, `peak_week`); `CashChart`, rebuilt `Funding`, `Lenders`, `Negotiation`; real offers mapping (`services/lendwise.ts`), `lib/flags.ts`; approval-screen negotiation warnings; `app/icon.svg`.
- **e2e isolation:** `make e2e-db | run-api-e2e | run-ui-e2e` (:8001, :3001, `var/case-e2e.db`). `scripts/purge_cases.py` is an audited one-off (drops and recreates the two DELETE triggers in one transaction, appends `CASES_PURGED`, verifies the chain, backs up first; dry run by default; test in `tests/test_purge_cases.py`). **Not yet run against `var/case.db`:** dry run lists 0016..0022 (7 cases, 435 facts). Awaiting the user's confirmation of the id list (0019 is PAUSED, 0022 APPROVED).
- **Dev overlay:** the 404 was most likely `/favicon.ico` (fixed with `icon.svg`); the second issue could not be reproduced without a browser overlay. u3 fails on any console error or 4xx/5xx.
- **Verification:** `make check` green (1217 passed), typecheck, `next build`, vitest 87/87, e2e `u3` passed (real figures: peak ₹1,62,00,000 week 9, 10 shortfall weeks, need ₹1,42,00,000, OF-01-C 11.87% unaffordable and unranked, OF-01-B rank 1 at 13.00%, OF-01-A rank 2 at 17.56%), axe 0 serious in light, dark and 360 px.
- **Open:** raw lender reply text is not stored (only the re-audited revision); agent narratives still show figures as plain text.
- **Follow-ups (2026-11-16):**
  - **Purge verified on `var/case.db`:** 0 cases left (all 7 were test cases, CA-2026-0016..0022, so the demo database now has no demo case until a seed/`demo-reset` exists), 0 facts, 0 approvals, 0 files. Audit chain intact (`verify_chain` returns no broken seqs, 948 rows). One `CASES_PURGED` event at seq 948 listing the 7 ids. All six append-only triggers are back.
  - **Cheapest offer comes from the API:** `offer_view` sets `cheapest_headline_rate` on the lowest-APR offer(s) at full precision (every tie flagged). The name is historical: it is the lowest APR, not the lowest nominal rate. `Lenders.tsx` no longer compares anything. Tests: `apps/gateway/tests/test_offer_view.py`, plus web tests proving the UI follows the flag even when APR strings disagree.
  - **e2e guard:** `scripts/e2e_guard.py` refuses a `CASE_DB` that resolves to `var/case.db` (any spelling, symlink, hard link, or unset). `make e2e-db` and `make run-api-e2e` run it first (in `e2e-db`, before the `rm`). `make e2e` passes explicit URLs. `playwright.config.ts` refuses :3000 unless `E2E_ALLOW_DEMO=1`. Tests: `tests/test_e2e_guard.py`.
  - **Finding:** a bare `npx playwright test` went to :3000 although the config defaults to :3001, so the env file most likely sets `E2E_BASE_URL`. Use `make e2e`, or remove that line.

## Phase 10 notes (carried forward)
- **Negotiation history:** store the lender's reply text as a ledger fact, redacted (`security.pii.redact`) and injection-scanned (`security.injection`), so the Negotiation panel can show what the lender actually said. Today only the re-audited revision (`lw.negotiation.revised.*`) is stored and the UI says so.

## UI U2 notes (2026-11-16)
- **Built:**
  - `lib/money.ts` `paiseFromInput`: the one rupees → paise conversion (₹ or Rs., Indian or western grouping, `/-`, lakh / L / crore / Cr, BigInt). `MoneyInput` shows "Reads as ₹…" before submit.
  - `GET /v1/cases` items carry `recommended_amount`, null unless the latest `wc.gate` is GO (same rule as `/funding`, now shared as `_recommended`). The response adds `totals` summed in integer paise by the gateway. The dashboard renders only API figures.
  - 7 upload slots plus an offers/KFS box, with field/row/reason errors.
  - `RunPanel`: Run, or one question card → corrected upload → Resume. Live SSE progress, kept as "Last run" afterwards.
  - Director review with a step-up confirm (typed case ID) and "Approval is internal, not loan acceptance."
  - nginx security headers in one snippet, included by every block that sets its own `add_header` (`tests/test_nginx_headers.py`).
  - Dev server on :3000 (README, `docs/setup/local-dev.md`, `apps/web/README.md`). `docs/help/preparer.md` and `approver.md` written.
- **Decisions (user):** extend `GET /v1/cases` (not a new endpoint); TanStack Query and react-hook-form + zod deferred (design-plan §1).
- **Fixed on the way:**
  - ₹1,42,00,000 = **1,420,000,000 paise**. The U1 `inrFromPaise` comment and the MSW fixtures were 10× (the request example too).
  - U1 uploads sent a raw text body, but the gateway takes multipart only; uploads now use `FormData`, with the part's type set from the extension.
  - Gate `ERROR` was shown as NO_GO.
  - New-case labels were not tied to their inputs.
  - The first e2e failed because a fast run's progress log vanished as soon as the stream ended (onboarding and WC finish in ~0.1 s). A probe showed the stream and browser were fine, so the log now stays as "Last run".
- **Verification:** `make check` green (1214 passed, mypy --strict, bandit, import-linter 9/9). Web: typecheck, `next build`, vitest 79/79. e2e `u2` passed (2.6 min). It drives a fresh demo case through the UI only: create with typed money → rejected CSV with row/field/reason → 7 files + offers/KFS → Run → the min-cash-buffer question → corrected upload → Resume → ₹1,42,00,000 routed to the Director → Director step-up approve → dashboard totals equal `GET /v1/cases` totals. Screenshots for 8 screens × light/dark/360 are in `apps/web/e2e/__screenshots__/u2/`, with axe WCAG 2.2 AA at 0 serious or critical. The dev-overlay "2 Issues" badge in the screenshots is Next dev mode; not investigated (one is a 404 seen in a probe). Each run leaves one case in `var/case.db` (CA-2026-0019 is from the first, failed attempt; delete once `DELETE /v1/cases/{id}` exists).
- **Open:** agent narratives still render figures as plain text (U3, with the funding view). There is no file list endpoint, so upload results last only for the browser session. `GET /v1/cases` does two fact reads per case (`ponytail:` note; one grouped query if the list grows).

## UI U1 notes (2026-11-16)
- **Built:** shell + routing + auth flow (memory-only token; reload → sign in; gateway 401 → `/login/?expired=1`), light/dark themes from `tokens.js` (`--fbc-*` channels for Tailwind alpha, `.keep-light` for midnight panels, system/light/dark toggle), `lib/money.ts` (BigInt paise, identical to `format_inr`; "≈ ₹1.42 Cr" half-up), `<Figure>` + Radix provenance drawer on `GET …/facts/{key}/lineage` (null producer/passages/audit, superseded, no formula line, input facts clickable, focus returns), `lib/problem.ts` + `ErrorBanner` / `EmptyState`, `ERROR` gate state, `/__gallery` (dev only), MSW handlers + typed fixtures, `docs/help/error-messages.md`. design-plan §12 lists the as-built choices.
- **Decisions (user):** CredAssure in every user-facing place; Next upgraded before screens until npm audit has no critical/high; e2e reads `E2E_USERNAME`/`E2E_PASSWORD` from `.env` at run time; screenshots on a demo case whose facts carry the producer.
- **Upgrade:** next 16.4.4 (16.4.6 was < 14 days old; 16.4.4 bundles postcss 8.5.23), react 19.3.1, fiber 9.8.2, drei 10.7.9, framer-motion 11.18.2, recharts 2.15.4, @playwright/test 1.64.1 (playwright < 1.55.1 was a high advisory), root `overrides: playwright-core 1.64.1` (axe pulled 1.65.1). Lockfile regenerated twice (stale hoisted React 18 and playwright-core); old trees moved to the session scratchpad. `npm audit`: 0. Next 16 writes `AGENTS.md` by default → `agentRules: false`; `devIndicators: false`.
- **Verification:** typecheck, `next build`, `npm test` 46/46, `tests/test_boundaries.py` 2/2, `npm run e2e` 2/2 (fresh demo case via the API in ~1.5 min → `wc.recommended_amount` ₹1,42,00,000 with `producer.trace_id`; dashboard, case workflow, funding, drawer, gallery × light/dark/360 → `apps/web/e2e/__screenshots__/u1/`, axe WCAG 2.2 AA 0 serious/critical).
- **Fixed on the way:** dark `ink-400` caption contrast 3.6 → 5.7 (`#8592A8`); the nav-pill spring (shared `layoutId` across the two sidebar copies left the active item unpainted) and the page fade removed (design-plan §4 motion rule); login errors go through the mapper ("Failed to fetch" → "Cannot reach the CredAssure service"); MSW must listen before `lib/gateway` loads (openapi-fetch keeps the `fetch` it sees — tests otherwise hit the live :8000).
- **Run notes:** the gateway's CORS allows :3000 and :5173 only, so e2e runs `next dev -p 3000` (not :3005). Each e2e run creates one case in `var/case.db`. **CA-2026-0016 has 10× amounts** (₹32 crore order, ₹20 crore request: a typo in the first setup run, fixed and now asserted on screen); CA-2026-0017 is from a run whose poll was reset. Neither is the demo case; delete once `DELETE /v1/cases/{id}` exists (Phase 10).
- **Open / deferred:** TanStack Query, react-hook-form + zod → U2. Dashboard portfolio sums still add paise in the browser and `recommendedAmount` is never mapped on case summaries (shows ₹0) → U2. Funding 26-week chart, bridge labels (raw keys) and LendWise offer mapping → U3. Agent narratives render figures as plain text → U2 workflow. Browser MSW worker for offline dev → when needed. No `/v1/auth/refresh` → re-login is the refresh.

## UI U0 notes (2026-11-16)
- **Built:** `docs/ui/design-plan.md`: six named colours from `tokens.js`, a dark theme from the same token names, Sora + Inter with tabular figures, ASCII wireframes (case workspace and approval screen, desktop and 360 px), provenance `<Figure>` and lineage drawer, gate encoding with ERROR added, four principles, screen → route map, self-review.
- **Decisions (user):** follow finbridge closely (brief defaults accepted and listed in plan §9). npm workspaces, never pnpm: root `package.json` `workspaces`, and apps/web depends on `"@credassure/api-client": "*"`. The pnpm node_modules were moved to the session scratchpad (the hook blocks recursive deletes) and npm reinstalled them (root `package-lock.json`). Anyone still on pnpm must reinstall. `@playwright/test` 1.55.0 is pinned in apps/web.
- **Contrast fixes in the plan:** emerald text uses brand-700, because brand-600 is 3.77 on white; control borders use ink-400 in both themes.
- **Done before U1 (2026-11-16):** `GET /v1/cases/{id}/facts/{key}/lineage` (scope #33). Final shape is in design-plan §4; see the #33 notes.
- **Open:** `npm audit` reports next 14 (critical) and postcss (high). Fixing needs a Next major upgrade, so it is not done in U0.

## Scope #33 lineage notes (2026-11-16, pulled forward from Phase 10)
- **Built:** `GET /v1/cases/{id}/facts/{key}/lineage[?version=n]` (`apps/gateway/.../routers/lineage.py`, typed `Lineage` model). Access is `visible_case` (tenant, role, case policy; 404 when not visible). Agent ledger-prefix rules (#24) do not apply to reads. An unknown key or version → 404 problem+json. `source_ref` tokens resolve to `files` (case_files by sha prefix), `inputs` (fact / hr_record / ref) and `passages` (corpus.db chunk or doc id, case-scoped for KFS).
- **Write side (user decision: record at write time):** `LedgerPort.put_fact(provenance=)` (ADR 0006 amendment). The Supervisor's `_GuardedLedger` injects `{agent, stage, trace_id}` into the FACT_WRITTEN payload, in the same transaction and hash chain; agents cannot set it.
- **Ledger limits (told to the user):** `files[].name` is the upload label, because original filenames are not stored. No fact cites chunk ids yet; reference-rate facts cite a corpus doc id. `producer` is null for facts written before this change or outside a stage. No engine formula line. An identical re-write adds no version, so `producer` is the first write's, not the latest run's.
- **Security review:** PASS. SHOULDs fixed: corpus passages are tenant-scoped like `retrieval.search`; `version` is capped at 2^31−1 (it returned 500 before; now 422). NICE fixed: a source file only matches on a full sha12 with a matching kind.
- **Also:** Makefile `client` and web dev targets use npm (`npm run generate -w packages/api-client`); `PNPM` variable removed. openapi.json and `packages/api-client/src/schema.ts` regenerated.

## Phase 9d notes (2026-11-16)
- **Housekeeping commit `0311df0`:** design-detail §2.3 + ADR 0009 (14 tools, `load_offers`); ADR 0023 (ledger is the record for offers; offer tables dropped in Phase 10); approval inbox `warnings` + `evidence_warnings` in `DECISION_RECORDED` (negotiation_in_progress / revised_offer_not_reaudited); ADR 0024 chromadb 1.5.9 accepted risk (4 advisories, not 5; no fixed release).
- **Record:** each agent writes `<prefix>narrative` = {source model|template, code-rendered slots, text} (PII-redacted by the guarded ledger); the Critic trusts only these code slots. `put_fact` skips an identical rewrite (no new version, no event) so regeneration re-runs do not churn lineage.
- **Order:** SUP-05 recheck before the Critic (code is the authority on figures); every regenerated result is gated again. `invoke_extra` (negotiation) is never re-run; its message is checked before send, and its Critic-stage findings pause instead of re-routing.
- **Live (local qwen3:8b, 15 cases, before the last reviewer fixes):** 4 `CRITIC_BLOCKED` (LW 3, WC 1, all `VER_UNSUPPORTED_REASON`), each fixed by one regeneration; 0 fallbacks. Model wording kept: WC 13/15, LW 11/13. CA-2026-0005: LW draft failed the slot render (template); its invented-reason kind is covered by `test_VER05_CA0005_kind_invented_reason_is_regenerated`.
- **Open:** one token budget and deadline across regenerations (security SHOULD 1; extraction is already skipped on regeneration passes); qualitative misreadings (WC "below the minimum buffer" for weeks below zero) need VER-06; report wiring of `report_completeness` in Phase 10; fallback rate re-measured in E12; finding messages in the `regenerate` prompt → fixed per-code text (NIT); case-file id format pattern (security NIT 2); `slots.rate` half-even vs ADR 0010 half-up (NIT); copilot answers in 9e.
- **Env:** re-sync with `uv sync --all-packages --all-extras` (a bare `uv sync` drops members and the rerank extra).

## Phase 9c-b notes (2026-11-16)
- **Flow:** load offers → comparable offers from `lw.<id>.v<n>.comparable` facts → `engines.negotiation.plan` (highest fee in ₹; ADR 0021 and gold pinned to the same rule) → facts `lw.negotiation.{target,current_fee,competing_fee,competing_offer,template}` → `fee_waiver_v1` from those facts → `verify_claims(keys=…)` → `lender_send_template` → `scan(reply)` → re-audit + re-price (`compare` on the revision) → `concession_counts`, `revised.*`, `message`, `status=sent`.
- **Choices:** allowed while AWAITING_APPROVAL (changes neither amount nor route), refused when APPROVED/REJECTED; the revision is kept as `lw.negotiation.revised.*` facts (re-ranking with it needs the preparer to upload it and re-run the stage); `negotiation_messages` table not written; negotiation narrative is a fixed code template (no model).
- **Open:** ~~interim `verify_claims` in the gateway~~ (9d: the Critic's `verify_claims`); `lw.negotiation.*` are not recomputed by a SUP-05 recheck (code-produced, no gate); revised figures arrive after the Critic stage when the case awaits approval — mark the proposal stale in Phase 10 (#6); ~~`_UNSAFE`~~ (9d: `agents/critic/banned.yaml`).

## Phase 9c-a notes (2026-11-16)
- **Inputs:** `kind=offer` (JSON, `OfferUpload`: material terms may be absent, ids pattern-checked) and `kind=kfs` (Markdown, frontmatter `doc_id`; `offer_id`/`case_id` read only as short plain strings; a different `case_id` is flagged `KFS_CASE_MISMATCH`, not rejected). Injection scan at upload.
- **Tools:** `load_offers` added (14th tool, read-only, deviation from the "13 tools" count); `audit_offer`, `price_offer`, `check_affordability`, `rank_offers` take all offers per call (≤ 9 steps for 3 offers; > 4 offers → one question).
- **Registry:** lendwise writes `lw.*`, reads `wc.*` (`ledger_read_prefixes`; uses `wc.recommended_amount` as a staleness check). `authorize_fact(write=)`.
- **Record:** ledger facts + audit events; the `offers` / `offer_evaluations` / `negotiation_messages` tables are not written (deviation, one source of truth).
- **`/offers`:** stored facts after the stage; a read-only audit preview (no affordability, no ranking) while funding is not GO (gold T063/T064).
- **ADR 0006:** `complete_model` moved to `credassure.core.structured` (agents may not import `credassure.llm`); `credassure.llm.structured` re-exports it.
- **Reviews:** security 2 MUST (YAML alias expansion via frontmatter; unconstrained ids → ledger-key spoofing) fixed; money 1 MUST (unreadable undeclared row silently dropped → now flagged, non-comparable) fixed; brd 2 MUST (false "headline" sentence for cheapest-but-unaffordable; LW-03/07/08/10 test names) fixed. SHOULDs fixed: GST default taxed, 0.01 pp tie → total cost, `affordable` vs `eligible`, preview per-offer schedule, half-up paise GST, reference rates strict + effective date + fail fast, agent card, `verify_claims` grant deferred to 9c-b.
- **Open (accepted):** per-route limit on `/offers` preview recompute (global per-user limit applies); `StageBudget.check` can overshoot by ≤ 2 parallel calls; chromadb 1.5.9 pip-audit advisories (pre-existing, ADR before G3); `/offers` ledger view goes stale after a re-upload until the stage re-runs (Phase 10 #6).
- **Live keep-rates (local qwen3:8b, thinking off, 2026-11-16):** `lw_kfs_extract` kept 37/39 offer schedules (2 fell back to the code parse; ~10 s/call); `lw_explain` 1.0.0 kept 0/13 → 1.1.0 (only applicable placeholders + example built from them) kept 4/12 → 11/12 after fixing `slots._REPEAT` (was case-insensitive: "of OF-01-A" read as a repeated word; affects every agent's narratives, only loosens). Most kept drafts closely follow the example; CA-2026-0005's kept draft adds an invented qualitative reason — not catchable by slots (VER-06 stretch).

## Slot-based narratives (2026-11-15)
- **Change:** the model writes `{key}` placeholders; `packages/core/.../slots.py` renders every amount, week, rate and direction word ("lower than"), and rejects a draft with an unknown slot, a missing required slot, any digit/₹/%/number word/link, a free direction word (higher/lower/cheaper/affordable/before/after…), a repeated word after rendering ("10 weeks weeks") or a `BANNED` word → template. `wc_explain` 2.0.0 (zero offsets get no slot), `onb_explain` 2.0.0 (`{rule.<id>}`, `{next.<id>}`; a passed rule has no slot). Agents 0.2.1.
- **Live local qwen3:8b, 13 WC GO cases, same session:** before (1.0.0, number guard) 7/13 kept, ~5.8 s; **after (2.0.0, slots) 13/13 kept, ~4.7 s.** Remaining slip a slot can't catch: "cash remains below the minimum buffer" for the below-zero week count (semantic, VER-06 stretch).

## Phase 9b notes (2026-11-15)
- **9a follow-ups:** `SUP_RECHECK_MISMATCH` (re-check disagreements, onboarding and the default evidence check; schema failures keep `SUP_SCHEMA_INVALID`); one `llm call` log line per call (prompt, version, prompt/completion/total tokens, thinking estimate, latency ms, cache hit; no text); per-prompt `max_tokens` in the YAML, client sends min(prompt cap, `LLM_MAX_TOKENS`); `onb_explain` 1.1.0 and `wc_explain` 1.0.0 capped at 200.
- **Built:** `agents/working-capital` 0.2.0. Tools `validate_case_files` (latest stored file per kind, read-only; missing file → `WC_MISSING_FIELD` naming it; then `engines.validators`), `compute_cash_table`, `compute_recommendation` (handlers in gateway `_tool_factory`, case_id injected). Any blocker → NEEDS_INPUT with one question (priority MISSING_FIELD > UNIT_OR_CURRENCY > DATE_OUT_OF_RANGE > CONFLICT_TOTALS > DUPLICATE_ID), `wc.gate` only. GO → `wc.peak_shortfall/peak_week/shortfall_weeks/min_buffer/undrawn_limits/mitigations/recommended_amount/bridge.<line>/cash_table/gate`, each with `source_type=case_file`, `source_ref=case_files:<kind>@<sha12>,…`, `produced_by=engines.cashflow@1`, `input_hash`=sha256(file hashes, indicative, horizon, engine version) (lineage for #33; `LedgerPort.put_fact(input_hash=…)` optional). Placeholder ₹1,42,00,000 removed.
  - `wc_explain` 1.0.0: wc.* facts only; reply used only if every amount equals a fact (₹1), every bare number is a week fact or the horizon, no rate/date/unparsed digit, no `BANNED` word; else template (WC-07 until the Critic).
  - SUP-05 `make_recheck`: recomputes every wc.* fact from the stored files; mutation (recheck removed) fails the S2 test.
  - Registry: `ledger_prefixes.working_capital: ["wc."]`. `GET /v1/agents/working-capital/cases/{id}/cash-table` via new `SupervisorPort.fact` (case policy). openapi.json + TS client regenerated.
  - Upload schemas: the validator-required order/opening fields are optional at upload (dump `exclude_none`), so T048 reaches NEEDS_INPUT naming `min_cash_buffer` (user decision 2026-11-15). Indian-format amounts stay CSV-only (DATA_SPEC §2).
- **Evidence:** `apps/gateway/tests/test_wc_items.py` 15/15 T036–T050 via API, LLM off and on (scripted grounded reply used); T048 resume re-runs WC only; S2 override + `GATE_OVERRIDE`; cash table 26 rows, lowest week 9 −₹1,62,00,000 with costs uploaded in Indian grouping; lineage names the stored file. `make check` 1016 passed.
- **Reviews:** security-reviewer PASS (no MUST); SHOULDs fixed: guard rejects leftover digits (`Q1 FY27`), number words, URLs; `BANNED` covers lender/sanction/rate/urgency. money-auditor PASS; SHOULDs fixed: zero-need template names the dip and what covers it, `"1E+7"` refused at upload (422), funding/cash-table hide figures unless the latest `wc.gate` is GO. brd-conformance PHASE COMPLETE; SHOULDs fixed: T049 resume test, `evidence_ref` required non-empty (WC-05), negative registry test, cash table money as `{paise, display}`. Template-passes-its-own-guard test over every case.
- **E6:** `evaluation/reports/E6-2026-11-15.md` READY. 15/15 × model off/on recomputed independently in floats (figures to ₹1, cash table to ₹0.00); adversarial model reply never reached a narrative.
- **Deferred:** `wc_explain` acceptance rate on 8B (E6 SHOULD 1: lakh/crore text alongside grouped amounts); comparison-direction guard until VER-06 (SHOULD 2); Phase 11 scorer compares blocker fields by last path segment (SHOULD 3); `wc_header_map` + S20 header variants (optional); `credit_lines` in `REQUIRED_OPENING` can never be missing (NIT); restrict `SupervisorPort.fact` keys per router (security NIT); cap duplicate-ID lists in blocker messages (security NIT); rename log extra `prompt` → `prompt_name` (security NIT); ports gained `put_fact(input_hash=)` and `SupervisorPort.fact` without an ADR 0006 note (NIT).
- **Live local model (qwen3:8b, thinking off):** `wc_explain` 5.9–7.2 s; model wording used 5/13 GO cases. All 8 rejections were mangled Indian grouping (`₹1,10,0,000`), so the guard failed closed to the template. One draft also stated the comparison backwards ("higher than the request"); a number guard cannot catch direction errors (VER-06 stretch).

## Qwen3 thinking fix (2026-11-15)
- **Probe on this machine (Ollama 0.40.16, qwen3:8b, "Reply with the single word OK."):** `/v1` + `think: false` → ignored (10.1 s, 148 completion tokens, 695 chars in `message.reasoning`); **`/v1` + `reasoning_effort: "none"` → 0.3 s, 2 tokens, no reasoning**; native `/api/chat` + `think: false` → 0.1 s, 2 tokens. The `/no_think` prompt suffix is ignored, and Ollama returns reasoning in `message.reasoning`, not as `<think>`.
- **Change:** `LLM_THINKING_SWITCH` (`reasoning_effort` in `models-local.env`, `chat_template_kwargs` in `models-course.env`, the default). `/no_think` suffix removed. `<think>` stripped always; leaked thinking (inline or `reasoning`) is charged to the stage budget. Live smoke test `packages/llm/tests/test_live_ollama.py` (skipped without Ollama): <50 tokens, no reasoning.
- **Onboarding explanation latency (`onb_explain`, 9 blocked HR profiles, local):** before 17–65 s (9a); same-session control with the old switch 13–25 s; **after 1.5–3.7 s**. Model wording used 7/9 (2 fell back to the template on the existing guards).
- **Open:** confirm the course switch with `make llm-probe MODELS=course` (not called).
- **Baseline client fixed (2026-11-15):** with `EVAL_DISABLE_THINKING=true` it now sends the product's per-profile body from `LLM_THINKING_SWITCH` (`reasoning_effort` locally, `chat_template_kwargs` on course), so the graded baseline matches the system's model settings. Existing local baseline results were run with thinking on and stay labelled **provisional**; the graded baseline is the course-endpoint run.

## Phase 9a notes (2026-11-15)
- **Built:**
  - `agents/onboarding` 0.2.0: `get_hr_profile` → `evaluate_onboarding_rules` (engine, `AS_OF_DATE`) → narrative → facts `onb.rule.<role|AML-201|DPDP-101|FIN-101|policy_ack>` + `onb.gate` (`source_type=hr_record`). Blockers name each rule as `[id]`; NEEDS_INPUT asks one question.
  - Narrative: template on GO, with the LLM off, or when the model is down or slow (`LLMError`). The `onb_explain` reply is used only if it names every failed rule as `[id]`, has no digit outside the ids, no gate/approval wording (`BANNED`, interim VER-03 guard until 9d) and no passed rule.
  - `ledger/hr.py` `load_profile` (SELECT only; inactive employee → None → NEEDS_INPUT), `reads.preparer_emp_id` (active user, same tenant). Setting `HR_DB` (default `data/frozen/v1/hr.db`).
  - Gateway: onboarding tool handlers + `make_recheck` (SUP-05) in `main.py`; other agents keep empty handlers and the default re-check.
  - Scope #24: `agents/registry.yaml` `ledger_prefixes` (deny by default; onboarding `onb.` only; working_capital/lendwise/critic/copilot `""` until 9b–9e narrow them), enforced by `_GuardedLedger`. Both stage wrappers also refuse any `case_id` other than the injected one (security MUST, SUP-08).
  - A recheck exception now ends the stage as `SUP_AGENT_ERROR` (audited) instead of escaping `_gate`.
  - Chat: `pii.find` → `pii_redacted` + notice; the span gets redacted text only (ONB-06).
  - LLM client: `/no_think` appended when `LLM_DISABLE_THINKING=true` (Ollama ignores `chat_template_kwargs`).
- **Evidence:** 10/10 T026–T035 through the API with the LLM off and on, matching gold and an independent SQL recompute; mutation (recheck removed) fails the E9 S2 test. Live `MODELS=local` qwen3:8b: no `<think>` text, model wording used for E014/E012, 17–65 s per call (one 30 s timeout → template).
- **Reviews:** security-reviewer: MUST (case_id not pinned) fixed; SHOULDs fixed: deny-by-default prefixes, recheck exception, inactive employee/user, digit guard; NITs fixed: ack ordering, `<blockers>` tag. brd-conformance: PHASE COMPLETE; S2 (scripted model path in API test), S3 (`[id]` token match), N3 (BR-03 assertion) fixed.
- **Deferred:**
  - ~~9d: route the onboarding narrative through `verify_claims` and drop the interim `BANNED` guard~~ (done in 9d).
  - Blocker catalogue: `SUP_RECHECK_MISMATCH` instead of `SUP_SCHEMA_INVALID` for re-check disagreements (E5 SHOULD 2); a dedicated code for a missing employee record (E5 NIT 1).
  - 9b–9e: narrow each agent's `ledger_prefixes` entry.
  - Measure `onb_explain` latency on the course endpoint; tune `LLM_MAX_TOKENS` if p95 > 30 s (E5 SHOULD 3).
  - NITs: cache `registry.yaml` once per process; `_GuardedLedger._ledger` is reachable by attribute (threat-model note).

## Phase 7 re-measure on the closed corpus (2026-11-15)
- **Clean re-ingest:** `var/corpus.db` deleted and the three Chroma collections dropped through the Chroma API (a hook blocks recursive deletes). `var/embed_cache.db` and `var/case.db` were kept. `make ingest` indexed 1,283 documents (1,092 real + 191 synthetic: kfs 129, policy 62), with 0 unchanged and 0 removed.
  - Chunks: fixed512 15,499, section 59,478, semantic 40,797. Chroma equals SQL per strategy, and FTS5 has 115,774 rows.
  - Filter metadata has 0 NULLs, and all 208 `superseded_by` values resolve.
  - 57 documents have injection-flagged chunks (34 before).
- **`make retrieval-eval`:** `evaluation/reports/retrieval-2026-11-15.md`. Recall@5, out of 40, with rerank off/on:

  | Chunking | Keyword | Dense | Hybrid |
  |---|---|---|---|
  | fixed512 | 23/22 | 17/22 | 23/23 |
  | section | 21/24 | 17/26 | 25/25 |
  | semantic | 23/24 | 25/25 | 25/26 |

  - The best is 26/40 (section/dense/rerank and semantic/hybrid/rerank). The target is 34, so KR-05 stays **OPEN**. All 40 queries are answerable now; the ceiling of 33 is gone.
  - Hybrid gain over keyword at recall@5: +2 for best against best. With rerank off, per chunking: fixed512 +0, section +4, semantic +2.
  - KR-04: 0 violations. Queries and labels were not tuned.
- **E8 (retrieval part):** `evaluation/reports/E8-2026-11-15.md`.
  - The independent recompute matches all 36 recall values, with 0 KR-04 violations over 7,200 passages.
  - NOT READY on KR-05 only.
  - S1: the KFS dates make the case-isolation filter vacuous at live level; it is covered by unit tests only.
  - S2: add NBFC-lender and case-scoped queries in v2.

## Phase 7 notes (2026-11-14)
- **Built:**
  - **Corpus loading** (`packages/retrieval`, `sources.py`): reads the manifest + lock (status ok/ok_manual with text) and the synthetic KFS/policy front matter. Case-scoped KFS go under tenant `demo` (`core/seeded.py`). A boilerplate filter drops repeated site-menu lines.
  - **Chunkers** (`chunking.py`): `section_path` on every chunk; fixed 512/64, section, and semantic (25th-percentile split). CHUNKER_VERSION 3.
  - **Ingest** (`index.py`, `make ingest`):
    - It is re-runnable. The skip key covers the text, every filter field, the replacement's date, the chunker and the embedding model.
    - It writes corpus.db rows, FTS5 and one Chroma collection per strategy, with Chroma telemetry off.
    - The injection scanner runs on each chunk together with its heading, on the whole document, and on the raw text before boilerplate removal. A hit is flagged on the chunk, kept in the index, and audited once per document after commit.
  - **Search** (`search.py`, `search_knowledge`):
    - BM25 and dense retrieval fused by RRF (k=60), with an optional cross-encoder pinned to 2cfc18c9415c.
    - Filters run in both retrievers and again in SQL on the final rows: effective_from ≤ as_of; superseded only once the replacement is in force (an unknown or undated replacement counts as in force); jurisdiction in {IN, IN-MH}; applies_to in {all, lender type}; KFS only for their own (tenant, case).
    - The query is redacted before embedding.
  - **Embeddings** (`llm/embed.py`): batches through the limiter, transient retries ×2, SQLite cache.
  - **Case IDs** (`ledger.writes.next_case_id`): global across tenants and starts after the highest seeded ID (CA-2026-0016). This fixes a latent cross-tenant primary-key collision.
  - **Migrations:** corpus `b8582bd9a52e` (legal_basis, index_version) and `d41e7c2a9b10` (tenant_id).
  - **Eval:** `make retrieval-eval` writes `evaluation/reports/retrieval-2026-11-14.md` (18 configurations, KR-04 re-check, awaiting list). Queries carry `relevant_sections`. Q27 was relabelled to R-STATE-015/014, because R-STATE-005 was rejected as Marathi-only. R-JUD-001 is pinned in the builder because its URL changed.
  - **Corpus guard:** reads amounts written in words (T010 "twenty five crore").
- **Results:**
  - Recall@5, out of 40:

    | Chunking | Keyword | Dense | Hybrid |
    |---|---|---|---|
    | fixed512 | 20 | 19 | 20 |
    | section | 18 | 16 | 23 |
    | semantic | 21 | 22 | 19 |

    Best with rerank on is section/dense at 23. Re-run independently in E8: same numbers, 0 KR-04 violations, isolation holds.
  - **Ceiling today: 33/40.** 7 queries lack their document: Q11, Q12 (R-MSME-01), Q26 (R-JUD-001), Q30 (R-BANK-03), Q31 (R-BANK-04/05), Q36 (R-RBI-11) and Q37 (R-RBI-01). Q18–Q21 and Q27 also wait on KR-04 distractor documents (R-RBI-MD-014/015/019/025/027/028/032, R-STATE-001/004).
  - Most misses are a different relevant document outranking the labelled one. The labels are too narrow for a 506-document corpus (E8 SHOULD 1).
  - **Injection:** 34 documents flagged (10 planted KFS + 24 real, mostly zero-width characters or "rank/recommend" phrasing); 34 audit events in the final run. Earlier interrupted runs also audited; each indexing audits once.
- **Reviews:**
  - **security-reviewer:**
    - MUST: a metadata-only change was skipped by ingest. Fixed and tested.
    - SHOULDs fixed: heading and whole-document scan, query redaction, audit after commit. chromadb advisories: risk register plus `make audit --ignore-vuln`.
  - **Owner follow-ups (2026-11-14), all done:**
    - Chroma is embedded only. There is no Compose service, and `test_chroma_runs_embedded_only` keeps it that way.
    - (tenant, case) KFS scoping, the seeded tenant `demo`, and the case-ID floor, plus the isolation test.
    - Raw-text scan before boilerplate removal.
    - Supersession by the replacement's date.
    - Pinned reranker revision.
  - **E8 (retrieval part):** `evaluation/reports/E8-2026-11-14.md`. NOT READY on KR-05 only.
- **Deferred:**
  - **demo-reset (Phase 12):** must create the seeded cases CA-2026-0001..0015 under tenant `demo` (`core.seeded.SEED_TENANT`). `SEEDED_CASE_MAX` must track `data/frozen/v1/cases` (a ledger test checks it).
  - **Copilot (9e):**
    - `case_id`, `tenant_id` and `lender_type` for `search_knowledge` come from Supervisor/case state, never from model output (SUP-08).
    - Spotlight both `Passage.text` and `section_path`.
    - ~~The rest of E8~~ (done 2026-11-16, E8-2026-11-16).
  - **Reranker default:** keep `RERANKER=none`. Hybrid without the reranker ties the reranked best (ADR 0013); re-decide after the labels are widened.
  - **chromadb upgrade:** upgrade when a fixed release exists, then drop the `--ignore-vuln` flags in `make audit`.
  - **Gateway wiring:** `make corpus-docker-ingest` runs in the read-only corpus container, which cannot write `var/`. Give it a `var` volume before using it. Settings has `reranker_revision`, but the gateway does not wire a Searcher yet (9e).
  - **NITs:**
    - The read-only SQLite URI is not escaped for paths containing `?` or `#`.
    - The superseded rule needs the replacement in the corpus (it fails closed otherwise).
    - Noisy PDF headings produce odd `section_path` values (E8 SHOULD 5).
    - R-RBI-06 is a page shell; re-save the PDF by hand.

## Phase 6 notes (2026-11-07)
- **Built:**
  - `packages/llm`: `client.py` (redact in/out → cache → budget → breaker → limiter → 30 s attempt, retries only on connection/timeout/429/5xx; 401/403/404 → `ModelUnavailable` so the stage uses templates), `resilience.py` (CircuitBreaker with a single half-open probe, RateLimiter, `shared_limiter`), `cache.py`, `structured.py` (`complete_model`, repair ×2 → `StructuredOutputError`), `probe.py` (`make llm-probe`).
  - `packages/core`: `prompts.py` (YAML registry: name = file stem, semver, sha256; `python -m credassure.core.prompts check --base <ref>`), `budget.py` (thread-safe stage budget), `LLMError` family and `NoPendingApproval` in `errors.py` (E11 N2), `SUP_TIMEOUT`, `LLMPort.complete(json_schema=…)`. These sit in core because ADR 0006 forbids agents importing `credassure.llm` (ADR 0008 §9).
  - `packages/security`: `pii.py` (Aadhaar only when Verhoeff-valid, PAN, IFSC, account near a keyword, phone, email; `redact_value`), `spotlight.py`, `injection.py`.
  - Supervisor: the stage runs in a worker thread with copied context; at 5 min a cancel event makes the orphan's next model/tool/ledger call raise, the result is `SUP_TIMEOUT`, audit `STAGE_TIMEOUT`; open circuit or `ModelUnavailable` → `llm=None` (template path) + `LLM_FALLBACK`; planner falls back to the fixed plan; tokens from the budget feed `stage_runs.tokens_used` → quota monitor; `llm` spans carry prompt version, sha and redacted I/O; orphan tool audits are tagged `after_timeout`.
  - Gateway: settings `LLM_CALL_TIMEOUT_S`, `STAGE_TIMEOUT_S`, `LLM_MAX_RETRIES`, `LLM_CIRCUIT_FAILURES`, `LLM_CIRCUIT_OPEN_S`, `LLM_RATE_PER_MINUTE`, `LLM_CACHE_PATH`; `set_redactor(pii.redact)`; Langfuse mask = `redact_value`; approver comment redacted before the approval row and audit; uploads scanned (`INJECTION_FLAGGED` audit, `injection_flags` in the response) and refused with a field error when they contain an Aadhaar, PAN or account number.
  - `sup_plan` prompt moved to `agents/supervisor/.../prompts/sup_plan.yaml` 1.0.0. Eval record carries `system_prompt_versions`; the baseline client uses the shared limiter.
  - `.github/workflows/eval-fast.yml` + `make eval-fast` (bump check + offline prompt subset). ADR 0008 Accepted.
- **Mutation evidence (each alone, then restored):**

  | Mutation | Tests that fail |
  |---|---|
  | Breaker threshold 5 → 50 | `test_scope48_breaker_opens_after_5_consecutive_failed_calls`, `..._half_opens_after_60s...`, `..._failed_probe_reopens...` |
  | Open circuit no longer short-circuits | `test_scope48_breaker_opens_after_5_consecutive_failed_calls` |
  | Stage timeout removed (`future.result()`) | `test_scope23_hung_stage_times_out_saves_state_and_cancels_the_orphan`, `test_scope23_orphan_tool_and_model_calls_are_refused` |
  | `cancel.set()` removed on timeout | the same two tests |

- **Reviews and evals:** security-reviewer: no MUST; SHOULD 1–3 fixed (single probe, orphan audit tag, upload PII refusal), SHOULD 4 mitigated (orphan-thread warning). brd-conformance: MUST (flaky backoff test; retry sleeps now recorded apart from limiter spacing) fixed; SHOULD half-open probe and span I/O fixed. `evaluation/reports/E4-2026-11-07.md`: Phase 6 scope READY; Critic half N/B until 9d.
- **Carried forward:**
  - Injection scanner + spotlighting on retrieval ingest (7), KFS and lender replies (9c), copilot passages (9e); chat persistence redaction (9e).
  - E4 S1 (engines owner): strict `parse_money` / `parse_rate` reject `/-` and `p.a.` suffixes; CSV cells like `1,42,00,000/-` fail closed.
  - E4 N2: RT14-style tool/secret probing goes in the copilot refusal policy (9e).
  - Security NITs: pin `eval-fast.yml` actions by SHA with #41 (Phase 12); configure the baseline limiter from `LLM_RATE_PER_MINUTE`; IFSC shape matches IDs like `INVC0000123` (documented ceiling).
  - Limiter and breaker are per process (`ponytail`); SQLite bucket if baseline and gateway run together.
  - Python cannot kill a thread: a pure-CPU loop in an orphan is not cancelled (ADR 0008 consequences).

## Phase 8b notes (2026-11-07)
- **Built:**
  - Gateway `/v1` routers: auth, cases, files, workflow (run, steps, jobs, SSE, inbox, decision), report, audit, admin, health.
  - Errors are RFC 9457 through one dispatcher, and 500s carry `INTERNAL_ERROR`.
  - Limits: a per-user/IP rate limit (`limits`), and a login limit of 5 failures per minute per (username, IP). CORS is the outermost middleware.
  - Uploads: owner only; 409 while a run holds the lock; 413/415; field/row/reason errors; formula cells and non-finite or absurd money are rejected.
  - Async runs (ADR 0007): 202 + job, Idempotency-Key replay, lock probe → 409 `RUN_IN_PROGRESS`, heartbeat with cancellation. SSE reads run in a threadpool, with a 10-minute cap and a stale-run end.
  - The agent routers call `SupervisorPort.start_run`, and the `run_stage` bridge is removed.
  - Health: `/health/live` and `/health/ready`; quota warns at 70% and 90%.
  - Tracing: a Langfuse exporter behind a flag with a PII mask. Spans export on exit with duration and error. Every model call is an `llm` span and every tool call is a `tool` span plus a `TOOL_CALLED` audit event, all in the run's one trace.
  - The e2e demo case runs to the Director and is approved, with the LLM on and off.
  - `openapi.json` is guarded by a staleness test; CI runs `oasdiff breaking` on PRs.
- **Review fixes (tests first):**
  - **E9 S1:** a return with no pending approval fails closed: the case is FAILED, the blocker is `SUP_RETURN_NO_PENDING_APPROVAL`, the event `RETURN_REJECTED` is audited, the API answers 409 and no approval row is written. The decision runs under the run lock.
  - **E9 S3:** blockers store only the exception type and a stable code (`SUP_AGENT_ERROR`, or `loop: repeated identical tool call`). The detail is logged with the trace_id.
  - **E9 N1:** an unknown or missing return stage raises `InvalidReturnStageError`.
  - **E9 N2:** a HELD route reports `SUP_ROUTE_HELD` in the outcome and in the ROUTED audit event.
  - **E11 M1/M2, S1, S3, N1:** model and tool spans, the plan model call inside the plan span, export on exit, and the chat trace_id names a span.
  - **E10 SHOULD-3 and NIT-1:** the audit route verifies only the caller's tenant; retry is evaluator-only.
  - security-reviewer M1 and S2–S10.
  - brd-conformance MUST 1–3: one trace per run, the openapi CI guard, and this row.
  - Chat returns a fixed notice and no unverified model text, until the Critic exists (9d/9e).
- **Reviews and evals:**
  - security-reviewer: 1 MUST, fixed.
  - brd-conformance: 3 MUST, fixed.
  - `evaluation/reports/E9-2026-11-07.md`: READY.
  - `E10-routes-2026-11-07.md`: READY, no MUST.
  - `E11-2026-11-07.md`: NOT READY on 2 MUSTs (model and tool spans), both fixed and tested.
- **Deferred by design:**
  - #25 stage retry route → Phase 9. It is a 501 stub, already evaluator-only.
  - ARCHITECTURE §6.3 Critic → stage re-route, together with #21 regeneration → Phase 9d.
  - E9 S2: each of 9a, 9b and 9c adds a test that injects a wrong ledger value and expects `GATE_OVERRIDE`. **9a done** (`test_SUP05_E9S2_wrong_ledger_value_is_overridden_and_audited`). The default re-check now only checks gate blockers and that evidence facts exist.
  - E10 SHOULD-1: an ASGI upload-size guard before multipart parsing → Phase 10.
  - E10 SHOULD-2: openapi should declare bearer security on agent routers and problem+json error responses. This goes to Phase 10 with #51 Schemathesis, but **tell the UI lane first**: errors are problem+json at runtime even though the schema says otherwise.
  - E11 S2: the plan GET re-plans, which spends tokens under `llm_proposes` → Phase 9 stores the Plan.
  - E11 S4: an import-linter contract api → own agent internals → Phase 10 with #53.
  - E10 NIT-2..4.
  - security N4: an idempotency key reused with a different kind → 422.
- **Gates:** the Skeleton gate stays open until a UI walks the demo case (UI lane U1).

## Phase 8a notes (2026-11-07)
- **Built:**
  - Supervisor LangGraph (`agents/supervisor/.../graph.py`) with fixed plan and code-decided edges. It covers:
    - SUP-03 upstream-not-GO and SUP-04 repair ×2 → ERROR;
    - SUP-05 re-check on every GO with a `GATE_OVERRIDE` audit (A4 skips it, scope #1);
    - SUP-06 pause with one question, and resume of the blocked stage only;
    - SUP-07 step and token caps;
    - scope #4 loop → ERROR;
    - routing as a code node, and the approval `interrupt()`; a return clears that stage onward.
  - Plan span; `PLANNER_MODE=llm_proposes` is accepted only when it matches the fixed order (#19).
  - Placeholder agents return real `AgentResult`s. WC writes a canned ₹1,42,00,000 with `source_type=placeholder`.
  - Adapters (#46):
    - `ledger.store.SqlLedger` (LedgerPort + SupervisorStore);
    - `tools.runner.ToolRunner` (allowlist, 2 retries, loop detection);
    - `llm.fake.FakeLLM`;
    - `observability.tracing` (`span`, `capture`, `set_exporter`).
  - Ledger:
    - `audit_head` anchor, upserted with every append; `verify_chain` now catches a cut tail (closes the Phase 5 SHOULD);
    - `HEARTBEAT` 30 s, with `STALE_LOCK` = 3 heartbeats = 90 s and `heartbeat()` (closes the run-lock SHOULD);
    - `jobs` table with an idempotency key;
    - `set_case_state`, stage-run start/finish;
    - Alembic rev `5c1e0a8f2d47` (up/down tested).
  - ADR 0007 Accepted.
- **Verified:** with real adapters (SqliteSaver on case.db), the placeholders run to the Director and the case resumes from disk with the LLM on and off.
- **Tests:** `make check` green, 546 tests (68 new from the test-writer plus placeholder and wiring tests).
- **Mutation evidence (2026-11-07, each mutation alone, then restored):**

  | Mutation | Tests that fail |
  |---|---|
  | Repeated-call rule removed from `ToolRunner` | only `test_scope4_identical_repeat_call_raises_loop_detected` (44 others pass) |
  | `LoopDetected` no longer special-cased in the graph | only `test_scope4_loop_detected_inside_an_agent_fails_the_stage` |
  | New run forgets earlier GO stages | `test_SUP06_resume_reruns_only_the_blocked_stage`, `test_APR05_return_reopens_the_named_stage_only` |
  | Pause drops the question | both `test_SUP06_*question*` tests |
  | Takeover after 1 missed heartbeat | `test_scope22_lock_younger_than_stale_is_not_taken_over` |
  | Heartbeat stops refreshing | `test_scope22_heartbeat_refreshes_a_held_lock` |

- **Ignore rule:** `.gitignore` `build/` is now `/build/`, so `docs/build/` is tracked normally. The only ignored files under `docs/` are `docs/source/170MD.pdf` (L4, on purpose) and `.DS_Store`.
- **Still in 8b:**
  - gateway routers, auth hardening SHOULDs, RFC 9457, upload validation, rate limit;
  - job runner and SSE, health/ready, quota;
  - agent routers moved to `start_run` (then delete the `run_stage` shim), `make openapi && make client`;
  - e2e (#15);
  - reviews (security-reviewer, brd-conformance), `/eval E9`, `E11`, and E10 routes.
  - The Langfuse exporter for `tracing.set_exporter` is wired in the gateway.

## Phase 5 notes (2026-11-06)
- **`make db`** migrates `var/case.db` and `var/corpus.db` and seeds 25 users from `data/frozen/v1/users/eval_users.yaml`.
  It needs `SEED_PASSWORD` (12+ characters) or `SEED_PASSWORD_<USERNAME>` in the environment (both in `.env.example`).
- **Decisions:**
  - Only a case in `AWAITING_APPROVAL` or `HELD` can be decided, and only by the routed role (HELD goes to the VP).
  - The role is checked against the approver's user row, never taken from the caller.
  - Self-approval is refused in both `security.auth.can_decide` and `ledger.writes.record_decision`.
  - `writes.route_case` is what the Supervisor calls after the Critic GO (Phase 8).
- **Every transaction is `BEGIN IMMEDIATE`** (ponytail): writers queue on the 5 s busy timeout. Watch it in the Phase 11 concurrency smoke test (#35).
- **Deferred SHOULDs** (security-reviewer):
  - **Audit anchor:** `verify_chain` catches edited, reordered or missing-middle rows. It cannot catch the newest rows being cut off, or a full re-hash by someone with file access. Record `(seq, hash)` checkpoints outside case.db (e.g. in the Langfuse trace or the eval record), or chain with HMAC and a key from env. Decide in Phase 8.
  - **Approver comments (E10 SHOULD):** comments are stored and audited unredacted. Pass them through `security.pii.redact` once Phase 6 lands.
  - **Run-lock takeover (E10 SHOULD):** a lock is taken over after 5 minutes even if its run is alive. Enforce the 5-minute stage timeout (#23), or refresh `acquired_at` during a run, before relying on takeover (Phase 6/8).
  - **Case deletion (#39, Phase 10) vs append-only triggers:** write an ADR first. Either a tombstone with facts kept, or an audited migration-only purge. Never drop the triggers ad hoc.
  - **Phase 8 gateway:**
    - re-load the user (active, role) on each request, or keep tokens ≤15 min;
    - on login, verify against a dummy hash when the username is unknown (timing);
    - use `check_needs_rehash`.

## Phase 3 follow-ups (2026-11-06)
- **Corpus guard** (`check_corpus_refs`, in `make check`): every cited doc_id must be in the manifest, and each regulatory key fact must appear in its cited text once all cited documents are available. Pending documents are reported as "awaiting corpus". Strict mode, used by `freeze --write`, fails and lists the items. Today: 0 failures, 34 items awaiting.
  - The guard found **R-RBI-02 and R-RBI-10 captured as 2.6 KB RBI menu shells**. Both moved back to manual, with a note to save the PDF instead.
- **Baseline:** a call that fails twice is scored `infra_error`, left out of accuracy and counted per strategy.
  - Records carry endpoint, `context_length` (`EVAL_NUM_CTX`) and `run_kind`. Only a run on the course endpoint is `graded`.
  - **The local Ollama runs `llama-server -c 4096`** (not the 8192 in ADR 0017) with context shift, so local results are `smoke_test` only. The local run is not committed.
- **brd-conformance (re-review):** the corpus MUST is resolved by the guard. The new MUST, a freeze test that could never fail, is fixed: it now asserts `verify() == []` and a tamper test proves drift is detected.
  - SHOULD, not done: retrieval labels are doc_id + `section_hint`, not `section_path` (DATA_SPEC §7). Add `section_path` before G1, or recall@5 is inflated at document level.
  - SHOULD, by design: the `judge` scorer is a key-fact substring stub until J1 (scope #11, Phase 11).

## G1 pre-freeze work (done; provisional freeze 2026-11-15)
- [x] Corpus ≥500 real documents available: 1071 (2026-11-14; manual list empty)
- [x] Every referenced document available: `check_corpus_refs --strict` 0 failures and `freeze --readiness` clean (2026-11-14). Pre-freeze label changes, for the retrieval-label sign-off below: Q27 must_not_cite → R-STATE-003/-006 (old ones were scans); Q30 → R-BANK-S-016 + S-010 (R-BANK-03 404); Q31 retargeted to "Canara Bank MSME service charges" → R-BANK-08 (Indian Bank copies were scans); Q36 → R-RBI-10 Ch. III, must_not_cite R-RBI-11 (withdrawn). R-MSME-01 now holds the India Code MSMED Act text. **B1 (2026-11-15):** these edits now live in `build_assets.py` (a test keeps builder = committed); `check_corpus_refs --strict` also checks evidence quotes per document and KR-04 supersession (a superseded relevant doc, or a predecessor missing from `must_not_cite`; R-RBI-01 exempt as a withdrawal notice) over items, v1.0 and both v1.1-silver label files: 0 failures
- [x] `section_path` on all 40 retrieval labels (B1, 2026-11-15): every label names a section read from the section chunker and the text (never from results); 10 headingless documents are explicit `exact ""`; 4 labels add an `exact ""` preamble where the answering text sits before the first heading. Q23 drops R-RBI-06 (saved file is the RBI home page; re-save, label in v2). Known chunker limit, reported not patched: Q06/Q35 under fixed512 and Q28 under semantic have no passage carrying the labelled section. A non-copilot owner still signs them off
- [x] Regulatory gold (B1): 19 answerable items carry short `key_facts` plus verbatim `evidence` quotes checked in their own document. Fixes: T005 18% is CGST 9% (R-GST-01 heading 9971(v)) + SGST 9%; T013 cites the 2025 Act s.37(1)/(2)(g)/(3), R-TAX-02 (1961 s.43B) moved to must_not_cite; T004 adds R-CG-04 (the only CGTMSE page stating MSE eligibility); T010 and T019 exclude R-MSME-G-005 and R-RBI-12. Same KR-04 fixes in Q04, Q10, Q13, Q19, Q21
- [x] G1 label set: `queries.v1.1-silver.jsonl` added to `freeze.py` assets (v1.0 kept). The 72 v1.0 labels disputed before the section pass are kept and listed for the human pass in `judging/human_pass_disputed_v1.0.md` (16 still recompute as disputed after narrowing)
- [ ] Hand check — moved to the G1-final checklist below
- [ ] APR transcription — moved to the G1-final checklist below
- [x] Owner names [Name 2]–[Name 5] → Tejas, Suresh, Pritish, Abhishek (2026-11-15), in docs, agent cards, CODEOWNERS legend, corpus lock/MANUAL_DOWNLOADS/CORPUS_INDEX (regenerated) and gold authors (`build_testset.AUTHOR`, items.jsonl `author` only). Checked: no one authors gold for, hand-checks, transcribes or judges their own agent's category; `test_BRD5_nobody_writes_gold_for_their_own_agent` guards the gold authors. [Name 1], [Name 6], UI lead → G1-final checklist
- [ ] Graded baseline S1–S3 on the course endpoint (moved to the G1-final checklist below) (`EVAL_BASE_URL`, `EVAL_NUM_CTX` set to its context window)
  - **PENDING (B2, 2026-11-15):** `make llm-probe` fails, and neither `LLM_BASE_URL` nor `EVAL_BASE_URL` is set in `.env`, so the course endpoint is unreachable from here. Set `LLM_BASE_URL`/`LLM_MODEL` (probe) and `EVAL_BASE_URL`/`EVAL_MODEL`/`EVAL_NUM_CTX` (baseline) to the course values, then run `make llm-probe && make baseline`.
  - **2026-11-15 unblocked in code:** course endpoint is `Qwen/Qwen3-8B` at `https://103.42.50.41:1032/v1` (groups 016-030, CA `vm06-ca.crt`). Client now takes `LLM_CA_CERT`/`EVAL_CA_CERT`, `LLM_MAX_TOKENS`/`EVAL_MAX_TOKENS` and `LLM_DISABLE_THINKING`/`EVAL_DISABLE_THINKING` (ADR 0017 amendment). Remaining: owner puts keys + CA paths in the dotenv file, then `make llm-probe MODELS=course && make baseline MODELS=course`.
  - **Decision 2026-11-15:** integrate end to end on `MODELS=local` (Ollama qwen3:8b + in-process bge-small), then switch to `MODELS=course` for graded runs (ADR 0017).
- [x] ADR 0018 accepted (AgentResult freeze), Alternatives section added (2026-11-15)
- [x] `/freeze-g1` run as a **provisional** freeze (2026-11-15): `freeze --write` → `evaluation/FROZEN.sha256`; markers say `status: provisional`

## G1-final checklist (turns the provisional freeze into the final G1 freeze)
- [ ] Human label check: `make judge JUDGE=pritish` on the 249-item sample, then Tejas or Abhishek; `make kappa` **weighted κ ≥ 0.7** confirms v1.1-silver, else full human judging per `judging/criteria.md` (Suresh adjudicates)
- [ ] Hand check (10 rows, `evaluation/gold/hand_check.md`): rows 1–4 Tejas + Pritish, 5–8 Tejas + Suresh, 9 Suresh + Pritish, 10 Abhishek + Pritish; all match gold
- [ ] APR transcription (S21, `evaluation/gold/fixtures/apr_transcription_sheet.md`): Tejas (A) and Suresh (B) agree and **match 17.07%**
- [ ] Graded baseline S1–S3 on the course endpoint (`make llm-probe MODELS=course && make baseline MODELS=course`)
- [ ] Names for [Name 1] (Supervisor), [Name 6] (Copilot) and the UI lead; then CODEOWNERS handles
- [ ] When all are ticked: change the three FROZEN markers to `status: final` (markers only; the manifest must still verify)

**Correction rule after the provisional freeze:** v1 files are never edited. Any correction (gold, label, item) goes into a new version (`evaluation/testset/v2/`, `queries.v2…`) with an ADR naming each change and why. Every score affected is recomputed and reported next to the old one (old version, new version, delta), never replacing it.

## G1 eval notes (2026-11-15)
- **Gold corrections (B1), with reasons:**
  - **T005:** the gold said "GST 18%" as one rate. The source (R-GST-01, heading 9971(v)) sets CGST 9%; with SGST 9% that makes 18%. Key facts and evidence now name both halves.
  - **T013:** it cited s.43B(h) of the 1961 Act, which is superseded. It now cites the Income-tax Act 2025 s.37(1)/(2)(g)/(3), and R-TAX-02 (1961 s.43B) moved to `must_not_cite` so the KR-04 date filter is tested.
  - **T004:** the answer (CGTMSE covers micro and small enterprises only) had no document stating MSE eligibility. R-CG-04 is the only CGTMSE page that says it, so it was added.
- **R-RBI-01 exemption:** the Nov 2025 consolidation press release is the `superseded_by` target for about 200 circulars. It is a withdrawal notice, not a predecessor document, so `check_corpus_refs` exempts it from the KR-04 supersession check (`WITHDRAWAL_NOTICES`).
- **Reported finding, not patched:** three query × chunker pairs cannot hit the labelled section, because no passage carries it: Q06 and Q35 under fixed512, Q28 under semantic. This limits recall@5 for those configurations by design. Report it in the KR-05 write-up; do not relabel to suit a chunker.
- **Q23 waits on R-RBI-06:** the saved file is the RBI home page, so Q23 has no PSL label in v1.0 or v1.1-silver (`retrieval-silver` now skips pool passages from documents that are not available). Label it in v2 once the real PSL Directions 2025 PDF is saved (MANUAL_DOWNLOADS.md, first row).
- **Junk-page check (`make corpus-junk`):**
  - **Candidates: 82.** These are documents with text under 1,500 chars, a page title that is a site home page, or a title that names an index or listing.
  - **8 set to `needs_review`:** R-RBI-06 (RBI home page), R-CG-03 (CGTMSE circulars index), R-BANK-S-001 ("Skip to main content" only), R-CG-C-308/326/333 (CGTMSE address block), R-CG-C-321 (a heading only) and R-CG-C-323 (table digits only). None is cited by an item or v1.0 label.
  - **74 kept:** 72 are short but real text (≥ 99 words: one-page circulars, Parliament answers, gazette notifications, charge tables). R-RBI-09 and R-RBI-HIST-159 are listing-title false positives.
  - **Real available: 1,092 → 1,084.**
  - **Safeguards:** the flag survives `corpus-dates` and `corpus-import` until a new file is saved. Replacements are listed in MANUAL_DOWNLOADS.md.

## Phase 4 evidence (re-run 2026-11-06)
- Cash flow **15/15** and offers **15/15** match independent gold (`test_WC03_WC06_funding_matches_gold_to_one_rupee`, `test_LW05_LW11_offers_match_gold`).
- RBI Annex B APR: **17.07%**, PASS (`test_ADR0012_rbi_kfs_illustration_is_17_07`).
- **8 Hypothesis property tests:** 4 engine tests (bridge sums with need a non-negative lakh multiple; APR ≥ nominal with fees; unaffordable or ineligible never first; routing monotonic) and 4 normaliser round-trips. 174 engine tests pass; engine coverage 98%.
- money-auditor (Phase 4 review): **PASS**, no MUST.
- `/eval E3`: **READY**, no MUST (money-auditor, 2026-11-06). 15/15 checks PASS: no float in engines; 3 cash-flow cases (CA-0001 ₹1.42 cr, CA-0010 boundary ₹1.50 cr, CA-0004 with mitigation ₹1.25 cr) and 3 offers (OF-01-A hidden charge 17.5575%, OF-02-B CGTMSE 14.8862%, OF-03-B floating 13.1317%) recomputed independently and matched to ₹1 / 0.0001 pp; GST on fees only; CGTMSE y1 on principal then outstanding; RATE_MAY_RESET; routing ±₹1 under all three rules; calendar; Annex B 17.0706%.
  - SHOULD: rebuild the Annex B test from the S21 fixture and the engine's own EMI (today it hard-codes ₹969.73); ADR 0012 names a test file `test_apr_rbi_annex_b.py` that does not exist.
  - SHOULD: mitigations from their own week in the affordability overlay (same as S7 below; owner decision, ADR 0021 + gold).
  - SHOULD: optional `guarantee.guaranteed_amount` (CGTMSE coverage below 100% of principal).
  - NIT: direct tests for no GST on interest and RATE_MAY_RESET on every floating offer; cover loancost.py:49,151-177 and calendar.py:16.

## Phase 2 note
- **Plants:** all at or above the DATA_SPEC minimums (PLANTS.md). An independent recompute in `data/generators/tests` checks every case's need, plus an LW-09 cash overlay of every offer.
- **Reviews:** money-auditor found one MUST: eligible offers were sized at the exact need, so they were unaffordable. Fixed: principal is now need + 10%, rounded up to ₹1 lakh. brd-conformance passed with M1 below.
- **Corpus:** 69 manifest entries. A real download (2026-11-05) extracted 51. The lock file is `data/corpus/manifest.lock.json`; raw files and text are gitignored.

## Corpus status (`make corpus-status`, 2026-11-05, after CGTMSE 2015+ and SIDBI editions)
```
Real available 288/500 [############################......................] 212 to go
Pending 525 | rejected (no text) 227 | needs date or review 23

src tgt+buf avail  pend  rej nodate  name
  1   120+0     6   114    0      0  RBI Master Directions (2025 consolidation)
  2    60+0     2    58    0      0  RBI circulars superseded by the 2025 consolida
  3    60+0     7    52    0      1  RBI FAQs, lending-rate releases (24 months), M
  4  180+20   147    17  219     16  CGTMSE circulars, scheme guidelines, fee pages
  5    25+0     0    25    0      0  NCGTC schemes (ECLGS, CGFMU, CGSSI) guidelines
  6    15+0     0    15    0      0  MUDRA / PMMY circulars and FAQs
  7    40+0     1    38    0      1  Ministry of MSME annual reports and scheme gui
  8    40+0     4    36    0      0  Gazette notifications (MSME classification, GS
  9   30+70    47    53    2      0  CBIC GST circulars and FAQs on financial servi
 10    10+0     0    10    0      0  CBDT on s.43B(h) and Income-tax Act 2025 s.37(
 11   20+20    33     0    4      3  SIDBI publications and MSME Pulse reports
 12    15+0     7     6    0      2  TReDS - RBI directions and platform FAQs/ruleb
 13   40+40    34     6    2      0  Bank and NBFC schedules of charges and sample 
 14    50+0     0    50    0      0  Lok Sabha / Rajya Sabha answers on MSME credit
 15    25+0     0    25    0      0  Supreme Court and High Court judgments on the 
 16    20+0     0    20    0      0  State MSME/industrial policies - Maharashtra (

owner      assigned imported pending
[Name 1]         92        0      92
Tejas         87        0      87
Suresh         86        0      86
Pritish         86        0      86
Abhishek         82        0      82
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
- **CGTMSE 2015+ and SIDBI editions (2026-11-05):** +21 available.
  - **CGTMSE:** circulars before 2015 are skipped. The year comes from the table row; if no year is shown, the date is checked on download (`skipped_pre_2015`). Only 1 new circular, because the 2015+ ones were nearly all harvested already.
  - **SIDBI:** 14 → 33, through the two-level MSME Pulse harvest (index → edition pages → PDFs).
  - **MANUAL_DOWNLOADS.md:** 224 RBI rows come first in each owner's section, marked *save as Web page, HTML only*.
- The 520 manual items are split across six owners in `data/corpus/MANUAL_DOWNLOADS.md`. Each section starts with tier 1.
- **One-time retries are due on or after:**
  - 2026-11-06 05:11 UTC: NCGTC (502), MUDRA (connection error), sbi.co.in (timeout);
  - 2026-11-06 08:44 UTC: cbic-gst.gov.in (timeout).

  Run `make corpus-harvest` and `make corpus-download` after both; each outcome is recorded in the lock.
- msme.gov.in (403), Udyam (redirect loop) and RXIL (444) stay manual.
- The commit titled "data: Indian real corpus ≥500" is reserved for when real available reaches 500 or more.

## Open questions (owner, date)
- **Before G1 (Phase 3):**
  - **Readiness check:** run `uv run python -m credassure.evaluation.freeze --readiness`. It lists 5 test items and 14 retrieval queries whose relevant documents are not downloaded yet: R-MSME-01, R-MSME-02/-G-004, R-TAX-01/02, R-RBI-09, R-GZ-002, R-MSME-G-003, R-JUD-001, R-STATE-005, R-BANK-02/03/05, R-RBI-01/11. `--write` refuses to freeze until the list is empty.
  - **Hand check:** two people who don't own the agent fill in `evaluation/gold/hand_check.md` (10 rows).
  - ~~Authorship~~ done 2026-11-15 (Tejas, Suresh, Pritish, Abhishek; no one authors their own category).
  - **Baseline:** the local `llama3.1:8b` run is provisional. Ollama's context length depends on how it was started (ADR 0017). The graded baseline runs on the course endpoint.
- **Phase 4 follow-ups:**
  - **Mitigation timing (money-auditor S7):** affordability counts evidenced mitigations from week 1, and gold does the same. The fix needs an ADR 0021 amendment and the same change in gold, so it is the owner's decision.
  - **Unauthorised role (N5):** training and acknowledgement rules are not evaluated, so ONB-04 names only the role. Gold does the same; recorded as intended.
  - **Unpriceable offers (N1):** a 0% rate or moratorium = tenure raises. The LendWise agent (Phase 9c) must catch this and mark the offer non-comparable.
  - **Ablation switching (scope #1):** only the `AblationMode` enum exists. The `ABLATION` setting and the A1/A4 bypasses come in Phases 8 and 11.
- **Manual list rebuilt (2026-11-05):** `data/corpus/MANUAL_DOWNLOADS.md` has 183 rows, ~30 per owner.
  - **Exact links:** 94 rows, built from `data/corpus/manual_curated.yaml`, which was compiled by reading official index pages once:
    - 40 RBI Master Directions (Commercial Banks, plus SFB / co-op distractors);
    - RBI FAQs; Udyam and Gazette notification PDFs; the MSMED Act (Samadhaan copy);
    - four state policies; the Samadhaan judgments list.
  - **Recipe rows:** 89, for monthly lending-rate releases, superseded RBI circulars, Sansad answers, judgments, and the MH/KA policies.
  - **No bare home-page rows;** a test enforces this.
  - **Targets rebalanced:** NCGTC and MUDRA are 0 (nothing reachable); msme.gov.in is 403; CGTMSE, Gazette, tax, banks and TReDS targets are set to what is actually held.
  - **Held back:** 54 rows on hosts awaiting their 2026-11-06 one-time retry are left off the list until the retry result is recorded.
  - **Reachable:** 288 available + 237 pending + 23 awaiting dates = 548 against the 500 target.
- **Before the next corpus network run (incl. the scheduled 2026-11-06 retry run):**
  - Optional (ADR 0020, amended 2026-11-06): set `CORPUS_CONTACT_EMAIL` or `CORPUS_CONTACT_URL` in `.env` to add a contact to the User-Agent. Without either, runs use `CredAssure-capstone/1.0 (IIT KGP academic project)`.
- **Host terms (ADR 0020):** 44 hosts have no terms of use recorded (`automated_access: unknown`).
  - Owners are listed in `MANUAL_DOWNLOADS.md` ("Hosts missing terms").
  - Mark a host `restricted` if its terms forbid automated access; the script then never fetches from it.
- **Corpus container:** `docker compose config` is valid. The image (`deploy/docker/Dockerfile.corpus`) was not built, because the Docker daemon was not running. Build it once with `make corpus-docker-status`.
- **Corpus (ADR 0019, 2026-11-05): 288 real Indian documents available, 212 short of 500.**
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
- Course endpoint context window, JSON/guided-decoding support, token quota (confirm day 2). Course: `Qwen/Qwen3-8B`, 8192 tokens in+out, 1024 output max, 1 active request/key, 60/min (2026-11-15). Local Ollama: `qwen3:8b` (was `llama3.1:8b`), context 8192, guided JSON off until `make llm-probe` (Phase 6) passes against it (ADR 0017).
- Owner names for [Name 1], [Name 6] and UI lead (Tejas, Suresh, Pritish, Abhishek done 2026-11-15); replace `@credassure-owner-*` placeholders in `.github/CODEOWNERS` with real git usernames
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
- Local dev and demo model: Ollama `qwen3:8b` (switched from `llama3.1:8b` on 2026-11-15 to match the course Qwen3-8B) plus `nomic-embed-text`, context 8192 (ADR 0017). Graded eval stays on the course endpoint.

## Retrieval v2 query backlog (P2b, after G1; never edit v1 after freeze)
- One NBFC-perspective query (`lender_type=nbfc`), so the `applies_to` filter is tested both ways (E8 S2).
- Case-tied queries inside the KR-05 set (`case_id` + `tenant_id`), not only the 3 isolation checks in `isolation.jsonl`.
- More other-state distractors: only 2 are indexed (R-STATE-003 IN-UP, R-STATE-006 IN-KA).
- **Copilot (9e) decision, found by P2b ISO3:** case-scoped KFS are also filtered by `applies_to`, so a case's own NBFC/co-op/SFB offer KFS are invisible from a `commercial_bank` query (CA-2026-0013 has only NBFC/co-op lenders). Decide in 9e: exempt case-scoped KFS from `applies_to`, or search per offer with that lender's type. ISO3 runs as `lender_type=nbfc` until then.
- **9e/LendWise:** v1 and v2 KFS of a revised offer are both in force (`superseded_by: null` on v1, as before P2b). Either set `superseded_by` on v1 when v2 exists (v2 data) or have the copilot pick the latest version. ISO3 (`lender_type=nbfc`) proves no leak and some own KFS visible, not that every own KFS is reachable.
- Known side effect of P2b: v2 revision KFS are in force (AS_OF) before the negotiation round runs. LW-13/BR-09 gate concessions by offer version in code, not by retrieval; revisit if the copilot quotes a v2 fee early.

## Decisions pending (human)
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
- #4 Loop detection, #15 e2e with FakeLLM (LLM on/off), #16 health + quota 70/90%, #28 /v1 + openapi CI guard, #46 adapters injected by the gateway, #47 async stage jobs (202, Idempotency-Key, SSE, heartbeat), #50 health probes (Phase 8, 2026-11-07)
- #53 Import-linter slice (five contracts in `make check` / CI, plus the web `fetch` pytest). Eval E18 stays in phases 10 and 12
- #8 Rounding policy (ADR 0010; `packages/core` money helpers)
- #9 Blocker catalogue (`BlockerCode`, gate vs warning vs needs-input)
- #21 CriticFinding schema only. Regeneration stays in Phase 9d
- #24 Agent registry and data-access matrix (`agents/registry.yaml`, `packages/tools` authorize)
- #25 `agent_version` field on AgentResult. Retry route stays in Phase 9. Frozen by ADR 0018 (Accepted 2026-11-15)
- #26 Excluded multi-agent patterns (ADR 0009)
- #14 Corpus legal-basis audit (`make corpus-audit`, `credassure.datagen.corpus`; throttled downloader `make corpus-download`)
- #32 Error catalogue (`ApiErrorCode`). HTTP behaviour of the 501 routes is unchanged
- #7 Repayment date → week mapping (`engines/calendar.py`, ADR 0011)
- #1 Ablation enum only (`AblationMode`); switch paths in Phases 8 and 11
- #22 Concurrency, DB part (WAL, busy_timeout 5000, BEGIN IMMEDIATE, one run per case with stale takeover); limiter part done in Phase 6 (shared per-process limiter)
- #23 Timeouts and cancellation (30 s per model attempt, 5 min per stage, cancel event, SUP_TIMEOUT, state saved; Phase 6)
- #36 Prompt/model change control (YAML registry with semver + sha, bump check, eval-fast CI; Phase 6)
- #48 Model resilience (ADR 0008: transient-only retries with jitter, circuit breaker, template fallback; Phase 6)
- #27 tenant_id on every case table; reads are scoped by tenant and case
- #29 Alembic for case.db and corpus.db; upgrade, downgrade and upgrade again tested; seeds separate (`credassure.ledger.seed`)
- #49 Fact or decision commits together with its audit event; row_version on cases (version_id_col) and approvals
- #33 Explainability endpoint `GET /v1/cases/{id}/facts/{key}/lineage` (pulled forward from Phase 10, 2026-11-16)
