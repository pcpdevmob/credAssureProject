# Manual entry: 08-no-loan-needed

Type this case into the web app by hand. Values come from frozen case CA-2026-0015. The same values are in `manual-entry.xlsx` next to this file, one sheet per screen; copy table rows from there and use **Paste rows from Excel**. How-to: `docs/setup/e2e-testing.md`, part 8. Expected result: part 9 of that guide.

## 1. New case

| Field | Type this |
|---|---|
| MSME legal name | Manual test 08 (synthetic) |
| PO reference | PO-CA-2026-0015 |
| Order value | 80,00,000 |
| Customer due date | 15 May 2027 |
| Requested amount | 2,00,00,000 |
| Documents | leave empty |

Press **Create case**. The case opens on the Documents tab.

## 2. Case data (Documents tab → Case data → **Fill in** on each section → **Save**)

### Customer order

| Field | Type this |
|---|---|
| Purchase order number | PO-CA-2026-0015 |
| Customer name | Customer Synthetic 15 |
| Order value | 80,00,000 |
| Order date | 2026-11-04 |
| Delivery weeks | 1, 4, 7 |
| Customer pays within (days) | 60 |
| Advance paid by the customer (%) | 10 |
| Business size (MSME class) | Small |
| Investment in plant and machinery | 18,00,00,000 |
| Annual turnover | 68,00,00,000 |
| Home state | Maharashtra |

### Opening cash and credit lines

| Field | Type this |
|---|---|
| Plan starts on | 2026-11-16 |
| Cash in hand and in bank | 17,27,000 |
| Minimum cash to keep at all times | 10,00,000 |

Existing credit lines:

| Lender | Type | Limit sanctioned | Amount used |
|---|---|---|---|
| Existing Banker (synthetic) | Term loan | 28,00,000 | 28,00,000 |
| Existing Banker (synthetic) | Overdraft | 67,00,000 | 7,00,000 |

Confirmed extra funds: none (leave empty)

### The five tables

| Section | Rows | Sheet in manual-entry.xlsx |
|---|---|---|
| Weekly costs | 156 | 4 Weekly costs |
| Expected receipts | 6 | 5 Expected receipts |
| Customer invoices due | 5 | 6 Customer invoices due |
| Supplier bills | 5 | 7 Supplier bills |
| Stock movement | 26 | 8 Stock movement |

For each: open the sheet, select the rows (with or without the header), copy, then in the section press **Paste rows from Excel**, paste, **Add these rows**, check, **Save**.

## 3. Lender offers (Documents tab → **Add an offer from the lender's PDFs**)

Pick each offer letter from `lender-pdfs/`. With the model off the form is empty: type the values below. Then pick the KFS PDF and the schedule of charges PDF, type the schedule rows (**Add a charge**), tick **I checked every field above against the lender's PDF**, press **Save this offer**. Repeat for each offer.

### OF-15-A: Damodar Capital NBFC (synthetic)

| Field | Type this |
|---|---|
| Lender name | Damodar Capital NBFC (synthetic) |
| Loan amount | 55,00,000 |
| Interest rate (% a year) | 11.9 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 24 |
| Moratorium (months) | 6 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 3,30,446 |
| Offer date | 2026-11-11 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-06-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 0% of the principal prepaid (R-BANK-03 range) |
| Type of lender | NBFC |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.76 | Yes |
| Documentation charges | Upfront | Fixed amount (₹) | 15,000 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.76% of the loan amount + GST |
| Documentation charges | Upfront | ₹15,000 + GST |

### OF-15-B: Ennore Credit NBFC (synthetic)

| Field | Type this |
|---|---|
| Lender name | Ennore Credit NBFC (synthetic) |
| Loan amount | 55,00,000 |
| Interest rate (% a year) | 12.1 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 24 |
| Moratorium (months) | 4 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 3,05,040 |
| Offer date | 2026-11-11 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-04-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 2% of the principal prepaid (R-BANK-03 range) |
| Type of lender | NBFC |

Fees (press **Add a fee** for each):

none

- Leave the fees empty and do NOT tick 'no fees': the letter does not state them (a missing term)

Schedule of charges rows (after picking the schedule PDF):

no schedule in this scenario (the app asks for it)

### OF-15-C: Hooghly Finance Ltd (synthetic)

| Field | Type this |
|---|---|
| Lender name | Hooghly Finance Ltd (synthetic) |
| Loan amount | 55,00,000 |
| Interest rate (% a year) | 11.9 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 18 |
| Moratorium (months) | 6 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 4,88,411 |
| Offer date | 2026-11-12 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-06-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | 0.6 |
| Prepayment terms | 0% of the principal prepaid (R-BANK-03 range) |
| Type of lender | NBFC |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.76 | Yes |
| Documentation charges | Upfront | Fixed amount (₹) | 7,000 | Yes |

- Tick: GST is charged on the guarantee fee

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.76% of the loan amount + GST |
| Documentation charges | Upfront | ₹7,000 + GST |

Faster alternative for offers: pick the nine files in `lender-files/` under **Add all the documents at once** instead of typing them. Both give the same comparison.
