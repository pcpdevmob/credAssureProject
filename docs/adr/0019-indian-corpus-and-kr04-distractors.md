# ADR 0019: Indian-only real corpus; KR-04 distractors are Indian

Status: Accepted · 2026-11-05 · approved by the project owner · Phases 2, 3, 7 · Scope #14 · KR-01, KR-04, BRD G2

## Context
Track B Pillar III asks for a real corpus of 500–2,000 documents, and BRD G2 asks for ≥500 indexed. The first manifest had
69 public entries. Four of them were US SBA pages (legal basis L6), used as "non-Indian" distractors for KR-04 ("no superseded
or non-Indian rule cited as current"). Foreign documents add licence and relevance noise and do not test what the copilot
actually gets wrong: citing a rule that exists in India but does not apply to this case.

## Decision
The acquisition rules (robots, pace, identification, blocks, retries, terms of use, ingestion safety) are consolidated in
ADR 0020, which governs where the two differ.

1. **Corpus scope.** Real documents come only from Indian public sources (16 sources, target 750, in
   `data/corpus/sources.yaml` and `docs/data/DATA_RESOURCES.md`). Legal bases are L1–L4; L6 is removed. Court judgments are L2
   (Copyright Act s.52(1)(q)(iv)). Synthetic KFS and policy documents (L5) are extra and never count toward 500.
   Real + synthetic stays ≤ 2,000.
2. **Manifest fields.**
   - `jurisdiction` is `IN` or a state code `IN-XX`.
   - `applies_to` is one of `commercial_bank | nbfc | sfb | coop_bank | all`.
   - `source` names the table row (1–16); `method` is `script` or `manual`.
   - The synthetic MSME's home state is Maharashtra (`order.json home_state: IN-MH`).
   - Each synthetic offer carries `lender_type`.
3. **KR-04 distractors are Indian.** There are three kinds:
   - **(a) Other states' policies:** MSME/industrial policies of other states (GJ, KA, TN, UP, TS).
   - **(b) Superseded RBI circulars:** circulars replaced by the November 2025 consolidation, with `superseded_by` set.
   - **(c) Rules for other lender types:** for example NBFC-only or co-operative-bank directions cited for a commercial-bank offer.
4. **Retrieval filter (Phase 7).** A passage may be cited as current only if:
   - `effective_from ≤ AS_OF_DATE`;
   - it is not superseded;
   - `jurisdiction ∈ {IN, home state}`;
   - `applies_to ∈ {all, lender type}`.

   The lender type comes from the offer the question is about; for case-free questions it defaults to `commercial_bank`.
5. **Collection method.**
   - Scripts honour robots.txt, make at most one request per second, and stop a host on 403, 429, 418 or a bot challenge.
     That host's documents go to `data/corpus/MANUAL_DOWNLOADS.md`.
   - No retries with spoofed headers and no headless browsers.
   - RBI, e-Gazette, incometaxindia and India Code are manual only.
   - Raw L3/L4 files stay gitignored. Only `manifest.yaml`, `manifest.lock.json` (hashes, status, legal basis) and
     `MANUAL_DOWNLOADS.md` are committed. `make corpus-verify` proves a teammate's raw folder matches the lock.
   - A document counts as *real available* only when its status is `ok` or `ok_manual` and its text is extracted.

## Owner decision 2026-11-05: 16 script-fetched RBI documents are kept (closed)
The first corpus run fetched 16 RBI documents by script on 2026-11-05, before this ADR made RBI manual-only. It honoured robots.txt, made at most one request per second and sent an honest User-Agent.
- The documents are R-RBI-02/03/04/05/06/08/08-DRAFT/10/12/13, R-RATE-01-*, R-RATE-02-REPO and R-CAL-01.
- The owner kept them. They carry `fetched_by: script_pre_adr0019` in the lock.
- Every later RBI document is manual.

## Follow-up rules (owner, 2026-11-05)
- **Dates:**
  - An available document (`ok` or `ok_manual`) must have `effective_from`; the audit errors without it.
  - `make corpus-dates` takes a candidate date from the first two pages: the letterhead first, then a labelled date, then a plain one. It reads Indian formats and Hindi month names, ignores page clocks, and sets `date_source: extracted`.
  - It lists every extracted date in `DATE_REVIEW.md`, with a seeded 10% sample for a human check.
  - A document with no date is `needs_date` and is not counted until a person dates it.
- **One retry:**
  - A host that failed with 502/503/504 or a connection error gets exactly one retry, no sooner than 24 hours later.
  - It is recorded in the lock as `host:<name>` with `retry_after` and `retry_outcome`.
  - 403/418/429/444, bot challenges, robots refusals and redirect loops are never retried.
- **CGTMSE paging:** stays scripted. It submits the page's own HTML form field (`pageNo`).
- **MANUAL_DOWNLOADS.md:**
  - Each owner's section starts with the tier-1 sources: RBI Master Directions, RBI FAQs, rates and press releases, CGTMSE replacements (circulars from 2015 onward) and Parliament answers.
  - Then come NCGTC, judgments, state policies, the Gazette and the rest.
  - Owners are stable once assigned.

## Date sources and plausibility (owner, 2026-11-05)
- **`date_source`:** every available document has one:
  - `curated`: a hand-curated manifest entry;
  - `human`: entered by a person, never recomputed;
  - `extracted`: page text — letterhead, then a labelled date, then the first plain date;
  - `wef`: "w.e.f." / "effective from" anywhere in the text;
  - `url`: a date in the URL or file name, where an upload folder `/YYYY-MM/` means day 1 of that month;
  - `pdf_metadata`: CreationDate, else ModDate;
  - `retrieved`: the retrieval date. Allowed only for bank and NBFC charge schedules (source 13), where it means *current as of* that date.
- **Order:** the chain runs in the order above (after `curated` and `human`). A document with no date from any of them is `needs_date`.
- **Plausibility:** a date before 1990-01-01 or after AS_OF_DATE is `needs_review` and does not count. A person confirms it with `date_confirmed: true`, or corrects it and sets `date_source: human`.
- **Checking:** a seeded 10% per `date_source` is flagged for a human check in `DATE_REVIEW.md`.

## How the BRD wording is still met
KR-04 says no superseded or non-Indian rule is cited as current. With an Indian-only corpus there is no non-Indian
document to cite. The test of the same behaviour, a filter that rejects a rule which is not in force for this case, moves
to the three Indian distractor kinds above. That test is harder, because these rules look as plausible as the right ones. The
BRD text is unchanged.

## Consequences
- **Phase 3:** the KR-04 eval items and the 40 retrieval-query labels are written under these rules. None existed or were
  frozen when this ADR was accepted.
- **DATA_SPEC S24:** the bad-citation plants use an other-state policy or an NBFC-only rule instead of a foreign document.
- **Corpus completion:** the manual sources depend on six owners working through `MANUAL_DOWNLOADS.md` and running
  `make corpus-import`. `make corpus-report` tracks the distance to 500.
