# RBI APR illustration — independent transcription sheet (S21, DATA_SPEC §8.4, ADR 0012)

Status: **form ready, not started** (prepared 2026-11-15 for G1).

`rbi_kfs_apr_illustration.yaml` holds transcription 1 (`status: draft_transcription_1`). G1 needs two more
transcriptions, made **independently and blind**, that agree with each other and with transcription 1.

| Transcriber | Role |
|---|---|
| **Tejas** | Transcriber A |
| **Suresh** | Transcriber B |

## Rules
- Open the source in a browser (the RBI PDF refuses scripted downloads with HTTP 403):
  - primary: RBI circular RBI/2024-25/18, 15 Apr 2024, **Annex B** (R-RBI-12):
    https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12663&Mode=0
  - cross-check: Commercial Banks – Responsible Business Conduct Directions 2025, **para 348(3)(i)** / Annex XIII
    (R-RBI-02): https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13140
- Do **not** open `rbi_kfs_apr_illustration.yaml` or this sheet's other column until your own column is complete.
- Copy every value exactly as printed (digits, decimals, units). Write "not stated" if the source does not give it.
- Note page or paragraph for each value.

## Values

| # | Field | Source location (page / para) | Transcriber A (Tejas) | Transcriber B (Suresh) | A = B? |
|---|---|---|---|---|---|
| 1 | Sanctioned loan amount (₹) | | | | |
| 2 | Tenure (months) | | | | |
| 3 | Repayment frequency and method (e.g. monthly EMI) | | | | |
| 4 | Days from sanction to first instalment | | | | |
| 5 | Interest rate (% p.a.) and type (fixed / floating) | | | | |
| 6 | Fee or charge collected by the lender (₹) | | | | |
| 7 | Third-party charges collected by the lender (₹) | | | | |
| 8 | Total fees and charges (₹) | | | | |
| 9 | Net disbursed amount (₹) | | | | |
| 10 | Instalment amount as printed (₹) | | | | |
| 11 | Total interest (₹) | | | | |
| 12 | Total amount to be paid by the borrower (₹) | | | | |
| 13 | APR as printed (%) | | | | |

## Comparison with transcription 1 (after both columns are complete)

Filled by Transcriber A and B together, now reading `rbi_kfs_apr_illustration.yaml`.

| # | Field in the YAML | Transcription 1 | Agrees with A and B? | Note |
|---|---|---|---|---|
| 1 | `inputs.sanctioned_amount` | | | |
| 2 | `inputs.tenure_months` | | | |
| 3 | `inputs.repayment` | | | |
| 4 | `inputs.repayment.first_repayment_days_after_sanction` | | | |
| 5 | `inputs.annual_rate_pct`, `inputs.rate_type` | | | |
| 6–8 | `inputs.fees_total` (and its comment) | | | |
| 9 | `inputs.net_disbursed` | | | |
| 10 | `inputs.instalment_displayed` | | | |
| 11 | `published.total_interest` | | | |
| 12 | `published.total_repayable` | | | |
| 13 | `published.apr_pct` | | | |

`inputs.instalment_exact` (969.73) is derived, not printed; it is checked by the engine and gold tests
(`test_ADR0012_rbi_kfs_illustration_is_17_07`), not by this sheet.

## Outcome
- All three agree: change the fixture's `status` to `transcribed` and add both names to its header comment.
- Any disagreement: write it below; the fixture stays `draft_transcription_1` and G1 waits.

| Field | A | B | Transcription 1 | Resolution |
|---|---|---|---|---|
| | | | | |

## Sign-off

| Transcriber | Signature / initials | Date |
|---|---|---|
| Tejas | | |
| Suresh | | |
