# Manual entry: 03-held-exactly-1-5-crore

Type this case into the web app by hand. Values come from frozen case CA-2026-0010. The same values are in `manual-entry.xlsx` next to this file, one sheet per screen; copy table rows from there and use **Paste rows from Excel**. How-to: `docs/setup/e2e-testing.md`, part 8. Expected result: part 9 of that guide.

## 1. New case

| Field | Type this |
|---|---|
| MSME legal name | Manual test 03 (synthetic) |
| PO reference | PO-CA-2026-0010 |
| Order value | 3,90,00,000 |
| Customer due date | 15 May 2027 |
| Requested amount | 2,00,00,000 |
| Documents | leave empty |

Press **Create case**. The case opens on the Documents tab.

## 2. Case data (Documents tab → Case data → **Fill in** on each section → **Save**)

### Customer order

| Field | Type this |
|---|---|
| Purchase order number | PO-CA-2026-0010 |
| Customer name | Customer Synthetic 10 |
| Order value | 3,90,00,000 |
| Order date | 2026-11-10 |
| Delivery weeks | 4, 7, 10 |
| Customer pays within (days) | 45 |
| Advance paid by the customer (%) | 5 |
| Business size (MSME class) | Small |
| Investment in plant and machinery | 13,00,00,000 |
| Annual turnover | 71,00,00,000 |
| Home state | Maharashtra |

### Opening cash and credit lines

| Field | Type this |
|---|---|
| Plan starts on | 2026-11-16 |
| Cash in hand and in bank | 19,98,000 |
| Minimum cash to keep at all times | 10,00,000 |

Existing credit lines:

| Lender | Type | Limit sanctioned | Amount used |
|---|---|---|---|
| Existing Banker (synthetic) | Term loan | 13,00,000 | 13,00,000 |
| Existing Banker (synthetic) | Overdraft | 45,00,000 | 15,00,000 |

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

### OF-10-A: Hooghly Finance Ltd (synthetic)

| Field | Type this |
|---|---|
| Lender name | Hooghly Finance Ltd (synthetic) |
| Loan amount | 1,65,00,000 |
| Interest rate (% a year) | 10.7 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 12 |
| Moratorium (months) | 3 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 19,16,037 |
| Offer date | 2026-11-14 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-03-18 |
| Insurance premium (if any) | 2,39,250 |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 0% of the principal prepaid (R-BANK-03 range) |
| Type of lender | NBFC |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 2.42 | Yes |
| Annual review fee | Yearly | % of the loan | 0.25 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 2.42% of the loan amount + GST |
| Annual review fee | Yearly | 0.25% of the loan amount + GST |

### OF-10-B: Indravati Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Indravati Bank (synthetic) |
| Loan amount | 1,65,00,000 |
| Interest rate (% a year) | 12.65 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 18 |
| Moratorium (months) | 6 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 14,71,027 |
| Offer date | 2026-11-14 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-06-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | 0.85 |
| Prepayment terms | 2% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Commercial bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.81 | Yes |
| Documentation charges | Upfront | Fixed amount (₹) | 7,000 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.81% of the loan amount + GST |
| Documentation charges | Upfront | ₹7,000 + GST |

### OF-10-C: Damodar Capital NBFC (synthetic)

| Field | Type this |
|---|---|
| Lender name | Damodar Capital NBFC (synthetic) |
| Loan amount | 1,65,00,000 |
| Interest rate (% a year) | 12.25 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 24 |
| Moratorium (months) | 6 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 10,08,121 |
| Offer date | 2026-11-13 |
| Disbursal date | 2027-02-01 |
| First repayment date | 2027-09-01 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 1% of the principal prepaid (R-BANK-03 range) |
| Type of lender | NBFC |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.79 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.79% of the loan amount + GST |

Faster alternative for offers: pick the nine files in `lender-files/` under **Add all the documents at once** instead of typing them. Both give the same comparison.
