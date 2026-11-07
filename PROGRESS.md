# CredAssure — Progress (Claude Code reads this first and updates it last)

## Current phase
Phase 4 is done (2026-11-05); the Phase 3 follow-ups landed on 2026-11-06 (corpus guard, baseline infra_error, freeze test). Phase 5 is done (2026-11-06). Phase 8a is done (2026-11-07). **Next is Phase 8b (gateway, agent routers, e2e, openapi, reviews), then Phase 6, which must redact approver comments before the audit write.** Still open:
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
| 3 Eval assets | done (G1 items below) | BRD §12–13, KR-05, VER-02, scope #13; ADR 0021 | phase-3 | Independent gold (floats + numpy_financial, no engine import, contract-enforced) reproduces every design need, every PLANTS offer tag and RBI Annex B 17.07%. 100 items (25/10/15/15/5/6/8/8/3/5), 40 retrieval queries, 20 red-team prompts, 12 S24 bad citations, scorers (₹1 / 0.01 pp, BRD failure classes), freeze script with readiness gate, run record (#13), baselines S1–S3. money-auditor PASS (no MUST); brd-conformance: only pre-G1 corpus MUST |
| 4 Engines | done | WC-01..06, LW-02..11/14, ONB-02/03, APR-01..03, BR-05/07/12; scope #1 (enum), #7; ADR 0011 | phase-4 | Pure Decimal engines. 15/15 cash-flow and 15/15 offer known answers match gold (worst APR 0.005 pp). RBI Annex B 17.07%. 20/20 onboarding profiles. 426 tests, engine coverage 98%. money-auditor PASS, brd-conformance PASS, no MUST. SHOULDs applied: IRR edge/bisection tests, `gst_rate` and `indicative` required (no silent defaults), strict Decimal in audit and negotiation, schedule terms material, fee compared in ₹, week<1 rows blocked, undrawn ≥ 0, routing rejects negatives, deterministic tie-break |
| 5 Ledger + auth | done | SUP-08, APR-04/05, ONB-05, NFR-07, OBJ-08, BR-05, BR-14; scope #22 #27 #29 #49 | phase-5 | `packages/ledger` (case.db + corpus.db models, Alembic up/down, append-only triggers, hash-chained audit, fact ledger, run lock, read-only hr.db, seed) and `packages/security/auth.py` (argon2id, JWT, case policy). 39 tests; 468 total. brd-conformance PHASE COMPLETE; security-reviewer 2 MUST fixed (decision only on AWAITING_APPROVAL/HELD and only by the routed role, at both layers). E10 (auth part, security-reviewer): 1 MUST fixed (re-routing could reopen an APPROVED or REJECTED case); after the fix 46/47 adversarial checks pass. The open one, tail truncation of the audit chain, is a SHOULD (see Phase 5 notes). Route checks are N/A until Phase 8 |
| 8a Supervisor + jobs + anchor | done | SUP-01..08, APR-01..03 wiring, OBJ-08; scope #1 (A4), #4, #19, #22, #46, #47 | phase-8a | Supervisor graph, placeholders, adapters, audit_head, heartbeat lock, jobs table, ADR 0007. 546 tests. Reviews and evals run with 8b |
| UI U0–U6 | todo | UI-01..09 | | React lane |

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

## G1 still needs (in this order, then `/freeze-g1`)
- [ ] Corpus ≥500 real documents available (`make corpus-status`; today 286 after the two RBI shells were re-queued)
- [ ] Every referenced document available: `uv run python -m credassure.evaluation.check_corpus_refs --strict` clean (34 items today), or replace those items or queries
- [ ] `section_path` on the 40 retrieval labels (brd-conformance SHOULD)
- [ ] Hand check by 2 people who don't own the agent: `evaluation/gold/hand_check.md`
- [ ] Second independent transcription of the RBI Annex B APR illustration (S21)
- [ ] Owner names for [Name 1]…[Name 6] and gold authors (no one writes gold for their own agent)
- [ ] Graded baseline S1–S3 on the course endpoint (`EVAL_BASE_URL`, `EVAL_NUM_CTX` set to its context window)
- [ ] ADR 0018 accepted (AgentResult freeze)
- [ ] then `/freeze-g1`

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
[Name 2]         87        0      87
[Name 3]         86        0      86
[Name 4]         86        0      86
[Name 5]         82        0      82
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
  - **Authorship:** gold authors are placeholders ([Name 2]…). Replace them, and confirm that nobody wrote gold for their own agent.
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
- #7 Repayment date → week mapping (`engines/calendar.py`, ADR 0011)
- #1 Ablation enum only (`AblationMode`); switch paths in Phases 8 and 11
- #22 Concurrency, DB part (WAL, busy_timeout 5000, BEGIN IMMEDIATE, one run per case with stale takeover). The limiter part is Phase 6
- #27 tenant_id on every case table; reads are scoped by tenant and case
- #29 Alembic for case.db and corpus.db; upgrade, downgrade and upgrade again tested; seeds separate (`credassure.ledger.seed`)
- #49 Fact or decision commits together with its audit event; row_version on cases (version_id_col) and approvals
