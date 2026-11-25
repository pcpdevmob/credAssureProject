# Manual entry: 05-missing-case-data-question

Type this case into the web app by hand. Values come from frozen case CA-2026-0013. The same values are in `manual-entry.xlsx` next to this file, one sheet per screen; copy table rows from there and use **Paste rows from Excel**. How-to: `docs/setup/e2e-testing.md`, part 8. Expected result: part 9 of that guide.

> **This scenario:** Leave **Minimum cash to keep at all times** empty: the funding check stops and asks for it. Answer on the question card (for example 10 lakh).

## 1. New case

| Field | Type this |
|---|---|
| MSME legal name | Manual test 05 (synthetic) |
| PO reference | PO-CA-2026-0013 |
| Order value | 2,84,00,000 |
| Customer due date | 15 May 2027 |
| Requested amount | 2,00,00,000 |
| Documents | leave empty |

Press **Create case**. The case opens on the Documents tab.

## 2. Case data (Documents tab → Case data → **Fill in** on each section → **Save**)

### Customer order

| Field | Type this |
|---|---|
| Purchase order number | PO-CA-2026-0013 |
| Customer name | Customer Synthetic 13 |
| Order value | 2,84,00,000 |
| Order date | 2026-11-05 |
| Delivery weeks | 3, 6, 9 |
| Customer pays within (days) | 45 |
| Advance paid by the customer (%) | 5 |
| Business size (MSME class) | Small |
| Investment in plant and machinery | 15,00,00,000 |
| Annual turnover | 79,00,00,000 |
| Home state | Maharashtra |

### Opening cash and credit lines

| Field | Type this |
|---|---|
| Plan starts on | 2026-11-16 |
| Cash in hand and in bank | 16,86,942 |
| Minimum cash to keep at all times | (leave empty) |

Existing credit lines:

| Lender | Type | Limit sanctioned | Amount used |
|---|---|---|---|
| Existing Banker (synthetic) | Term loan | 16,00,000 | 16,00,000 |
| Existing Banker (synthetic) | Overdraft | 27,00,000 | 7,00,000 |

Confirmed extra funds: none (leave empty)

### The five tables

| Section | Rows | Sheet in manual-entry.xlsx |
|---|---|---|
| Weekly costs | 156 | 4 Weekly costs |
| Expected receipts | 6 | 5 Expected receipts |
| Customer invoices due | 4 | 6 Customer invoices due |
| Supplier bills | 5 | 7 Supplier bills |
| Stock movement | 26 | 8 Stock movement |

For each: open the sheet, select the rows (with or without the header), copy, then in the section press **Paste rows from Excel**, paste, **Add these rows**, check, **Save**.

## 3. Lender offers (Documents tab → **Add an offer from the lender's PDFs**)

Pick each offer letter from `lender-pdfs/`. With the model off the form is empty: type the values below. Then pick the KFS PDF and the schedule of charges PDF, type the schedule rows (**Add a charge**), tick **I checked every field above against the lender's PDF**, press **Save this offer**. Repeat for each offer.

### OF-13-A: Ennore Credit NBFC (synthetic)

| Field | Type this |
|---|---|
| Lender name | Ennore Credit NBFC (synthetic) |
| Loan amount | 1,32,00,000 |
| Interest rate (% a year) | 12.55 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 24 |
| Moratorium (months) | 4 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 7,31,862 |
| Offer date | 2026-11-10 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-04-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 2% of the principal prepaid (R-BANK-03 range) |
| Type of lender | NBFC |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.8 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.8% of the loan amount + GST |

### OF-13-B: Ghaghara Co-operative Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Ghaghara Co-operative Bank (synthetic) |
| Loan amount | 1,32,00,000 |
| Interest rate (% a year) | 12.75 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | (leave empty) |
| Moratorium (months) | 4 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 10,19,711 |
| Offer date | 2026-11-13 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-04-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 2% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Co-operative bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.99 | Yes |

- Leave Tenure empty: the letter does not state it (a missing term)

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.99% of the loan amount + GST |

### OF-13-C: Hooghly Finance Ltd (synthetic)

| Field | Type this |
|---|---|
| Lender name | Hooghly Finance Ltd (synthetic) |
| Loan amount | 95,00,000 |
| Interest rate (% a year) | 12.55 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 24 |
| Moratorium (months) | 5 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 5,53,923 |
| Offer date | 2026-11-11 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-05-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 2% of the principal prepaid (R-BANK-03 range) |
| Type of lender | NBFC |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.96 | Yes |
| Documentation charges | Upfront | Fixed amount (₹) | 6,000 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.96% of the loan amount + GST |
| Documentation charges | Upfront | ₹6,000 + GST |

Faster alternative for offers: pick the nine files in `lender-files/` under **Add all the documents at once** instead of typing them. Both give the same comparison.
