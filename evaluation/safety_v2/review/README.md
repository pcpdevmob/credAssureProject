# safety_v2 review record (K5, ADR 0031)

| | |
|---|---|
| Reviewer | Tejas (`tejast12`) |
| Sheet | `K5_Safety_Suite_Review_signed_Tejas.xlsx` (as returned, unedited) |
| Signed | "I read all rows I did not skip, and the suite may be frozen": **Yes**; rows skipped: none |
| Date on the sheet | 24/11/2025. The sheet was created on 25 Nov 2026 and returned that morning, so the date is a typo; the reviewer confirms the date in the freeze PR |
| Frozen | 25 Nov 2026, `freeze --reviewed-by "Tejas (tejast12)"` → `items.jsonl`, `FROZEN.sha256`, before any run |

## What the review decided
- **S38** renamed "Northeast Tribal Weavers Electronics" → **Brahmaputra Circuits LLP** ("Tribal" is a label; the name
  did not read as an electronics firm); Assam, the customer and the suppliers kept. Same change in
  `tests/e2e/test_fairness_invariance.py`. Applied in PR #58 before the freeze.
- **S16, S17** keep the pass rules edited on 25 Nov (no bare "ranked first"; only claims of an approval). Already in
  PR #58.
- **Q1**: S16/S17 reach the document library through chat only; no planted document (a re-index could move frozen
  scores). The limit is stated in the report.
- **Q2**: fairness rows S36–S40 are a fair spread of gender, community and region, with the S38 change.
- **Q3**: no attack missing that is worth replacing an item for; a cross-case read is not in the suite (covered by the
  3 isolation items of the 100-item set).
- Every other row: OK. S20 (Hinglish) kept as written: a fail there is a real gap, reported as such.

## Row alignment
In the returned sheet each answer sits one row above the item it describes (the waived-fee note on S11 belongs to S12,
the Hinglish note on S19 to S20, the Assam rename on S37 to S38). The decisions above are read with that shift, which
the content of each note makes unambiguous; the reviewer confirms this reading in the freeze PR. Under that reading
S01 has no explicit verdict; the reviewer confirms S01 as OK in the same PR.
