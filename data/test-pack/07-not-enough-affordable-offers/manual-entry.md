# Manual entry: 07-not-enough-affordable-offers

Type this case into the web app by hand. Values come from frozen case CA-2026-0005. The same values are in `manual-entry.xlsx` next to this file, one sheet per screen; copy table rows from there and use **Paste rows from Excel**. How-to: `docs/setup/e2e-testing.md`, part 8. Expected result: part 9 of that guide.

## 1. New case

| Field | Type this |
|---|---|
| MSME legal name | Manual test 07 (synthetic) |
| PO reference | PO-CA-2026-0005 |
| Order value | 4,09,00,000 |
| Customer due date | 15 May 2027 |
| Requested amount | 2,00,00,000 |
| Documents | leave empty |

Press **Create case**. The case opens on the Documents tab.

## 2. Case data (Documents tab → Case data → **Fill in** on each section → **Save**)

### Customer order

| Field | Type this |
|---|---|
| Purchase order number | PO-CA-2026-0005 |
| Customer name | Customer Synthetic 05 |
| Order value | 4,09,00,000 |
| Order date | 2026-11-13 |
| Delivery weeks | 5, 8, 11 |
| Customer pays within (days) | 30 |
| Advance paid by the customer (%) | 10 |
| Business size (MSME class) | Small |
| Investment in plant and machinery | 8,00,00,000 |
| Annual turnover | 65,00,00,000 |
| Home state | Maharashtra |

### Opening cash and credit lines

| Field | Type this |
|---|---|
| Plan starts on | 2026-11-16 |
| Cash in hand and in bank | 21,88,104 |
| Minimum cash to keep at all times | 10,00,000 |

Existing credit lines:

| Lender | Type | Limit sanctioned | Amount used |
|---|---|---|---|
| Existing Banker (synthetic) | Term loan | 17,00,000 | 17,00,000 |
| Existing Banker (synthetic) | Overdraft | 55,00,000 | 15,00,000 |

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

### OF-05-A: Indravati Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Indravati Bank (synthetic) |
| Loan amount | 1,63,00,000 |
| Interest rate (% a year) | 12.8 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | (leave empty) |
| Moratorium (months) | 6 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 14,54,343 |
| Offer date | 2026-11-14 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-06-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 0% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Commercial bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.75 | Yes |
| Documentation charges | Upfront | Fixed amount (₹) | 12,000 | Yes |

- Leave Tenure empty: the letter does not state it (a missing term)

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.75% of the loan amount + GST |
| Documentation charges | Upfront | ₹12,000 + GST |

### OF-05-B: Brahmaputra Industrial Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Brahmaputra Industrial Bank (synthetic) |
| Loan amount | 1,63,00,000 |
| Interest rate (% a year) | 12.75 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 18 |
| Moratorium (months) | 6 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 14,56,360 |
| Offer date | 2026-11-13 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-06-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 1% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Commercial bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 1 | Yes |
| Documentation charges | Upfront | Fixed amount (₹) | 8,000 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 1.00% of the loan amount + GST |
| Documentation charges | Upfront | ₹8,000 + GST |

### OF-05-C: Falgu Merchant Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Falgu Merchant Bank (synthetic) |
| Loan amount | 1,48,00,000 |
| Interest rate (% a year) | 11.2 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 6 |
| Moratorium (months) | 0 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 25,47,868 |
| Offer date | 2026-11-14 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2026-12-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 2% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Commercial bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.2 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.2% of the loan amount + GST |

Faster alternative for offers: pick the nine files in `lender-files/` under **Add all the documents at once** instead of typing them. Both give the same comparison.
