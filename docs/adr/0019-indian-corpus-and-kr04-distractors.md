# ADR 0019: Indian-only real corpus; KR-04 distractors are Indian

Status: Accepted · 2026-11-05 · approved by the project owner · Phases 2, 3, 7 · Scope #14 · KR-01, KR-04, BRD G2

## Context
Track B Pillar III asks for a real corpus of 500–2,000 documents, and BRD G2 asks for ≥500 indexed. The first manifest had
69 public entries. Four of them were US SBA pages (legal basis L6), used as "non-Indian" distractors for KR-04 ("no superseded
or non-Indian rule cited as current"). Foreign documents add licence and relevance noise and do not test what the copilot
actually gets wrong: citing a rule that exists in India but does not apply to this case.

## Decision
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

## Pending owner decision: 16 RBI documents fetched by script
On 2026-11-05, before this ADR made RBI manual-only, the first corpus run fetched 16 RBI documents by script. That run
honoured robots.txt, made at most one request per second and sent an honest User-Agent. The documents are R-RBI-02/03/04/05/06/08/08-DRAFT/10/12/13,
R-RATE-01-*, R-RATE-02-REPO and R-CAL-01. They keep status `ok`, and each lock entry carries a `provenance` note.
The owner chooses one of two options:
- **Keep them:** this ADR then records the acceptance.
- **Re-save by hand:** save each one in a browser and run `make corpus-import`, which makes them `ok_manual`.

Until the owner decides, they count as available.

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
