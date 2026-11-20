# ADR 0026 — KR-04 data correction: three outdated documents tagged superseded

Status: Accepted · Date: 2026-11-17 · Phase 10b · Requirements: KR-04, KR-05, CP-01

## Context
E8 (`evaluation/reports/E8-2026-11-16.md`) found two outdated passages (T003, T010), and the Phase 10b
baseline run showed T003 now citing a third. The copilot could cite all of them as current. All three had `superseded_by: null`, so the KR-04 filter (not superseded as of
`AS_OF_DATE`) let them through. This is a defect in the corpus metadata, not in retrieval code.

## Decision
Tag each document `superseded_by` its successor in `data/corpus/manifest.yaml`. Each tag rests on the
**documents' own text**: the old document states the old rule, and the successor states the rule that
replaced it. Test items, gold answers, `evaluation/testset/v1` and `evaluation/retrieval/v1` were not
opened or changed for this. The ingest derives `superseded_from` from the successor's `effective_from`
(`retrieval/index.py`), so each document drops out of current answers from that date.

| Document | Old text (its own) | `superseded_by` | Successor's text |
|---|---|---|---|
| R-CG-C-274 — CGTMSE Credit Guarantee Scheme for Co-Lending (CGSCL), w.e.f. 25 Feb 2022 | "The cap of ₹200 lakh or ₹100 lakh, as applicable for secured and unsecured loans respectively, is the maximum guarantee coverage limit per borrower under CGSCL" | R-CG-C-396 (revised CGSCL scheme document) | "not exceeding ₹500 lakh for credit facility secured by Primary Security"; "The cap of ₹500 lakh & ₹200 lakh is the maximum guarantee coverage". R-CG-C-199 also records "Circular No. 235/2023-24 dated December 18, 2023 regarding increase in the Ceiling of Guarantee from ₹200 lakh to ₹500 lakh". |
| R-SIDBI-P-008 — SIDBI Annual Report 2019-20 (Part I) | "The revised criteria for classification as MSME …": Micro ≤ ₹1 cr / ₹5 cr, Small ≤ ₹10 cr / ₹50 cr, Medium ≤ ₹50 cr / ₹250 cr (MoMSME notification of 1 June 2020) | R-MSME-02 (S.O. 1364(E), 21 Mar 2025) | Amends "notification … number S.O. 2119 (E), dated the 26th June, 2020" and "shall come into force with effect from the 1st day of April, 2025" (the ₹2.5/₹10, ₹25/₹100, ₹125/₹500 crore limits). The 2020 notification itself is already R-MSME-03 → R-MSME-02. |
| R-CG-C-237 — CGTMSE AGF payment by Government of Rajasthan under BRUPY 2022, guidelines (8 Sep 2022) | "Not exceeding ₹200 lakh … This limit of ₹200 lakh is likely to be increased shortly"; "Present limit is ₹200 lakh and same is subject to modification from time to time as per Credit Guarantee Scheme" — its cap is the CGS-I ceiling of the day | R-CG-05 (CGTMSE FAQ, credit facilities and parameters, 1 Apr 2025) | "credit facilities up to ₹10 crore per eligible borrower are covered under the guarantee scheme" |

No other document was changed. Method: the documents E8 names for T003/T010, plus every document the
baseline copilot run (Phase 10b, before) cited for those two items: R-CG-C-237 for T003 and R-SIDBI-P-008
for T010. Each was checked against its own text only.

## Consequences
- The whole annual report R-SIDBI-P-008 leaves current answers, not only its MSME-limits page. The
  rest of it is FY 2019-20 performance data, which is historical and not a rule the copilot should cite
  as current.
- `make ingest` re-indexes only the three changed documents (their `index_version` changes).

## Measurements (2026-11-17; same model qwen3:8b, corpus and settings; `make ingest`: 3 indexed, 1272 unchanged)
| Measure | Before | After |
|---|---|---|
| KR-05 `make retrieval-eval`, best configuration (section / hybrid / rerank off), recall@5 | 23/40 | 23/40 |
| Other configurations | — | fixed512/keyword/rerank-on 19 → 18; semantic/dense 19 → 20; the rest unchanged |
| Copilot regulatory set (`make copilot-live ARGS="--only regulatory"`) | 9/25 | 8/25 |
| T003 cites | R-CG-C-237 (outdated ₹200 lakh cap) | R-CG-C-406 (still fails) |
| T010 cites | R-SIDBI-P-008 (2020 limits) | nothing (still fails) |

The correction does what KR-04 asks: no outdated document is cited as current for T003 or T010. It does
not lift the score, because retrieval still misses the current passage (KR-05 stays OPEN at 23/40). The
one item that changed the other way, T015 (pass → fail), cites the repo-rate documents in both runs
(R-RATE-02-REPO before, R-RATE-02-BOB after). None of the three changed documents is involved, so this is
run-to-run model variance, not an effect of this change.
