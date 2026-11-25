# Manual entry: 02-vp-route-negotiation

Type this case into the web app by hand. Values come from frozen case CA-2026-0006. The same values are in `manual-entry.xlsx` next to this file, one sheet per screen; copy table rows from there and use **Paste rows from Excel**. How-to: `docs/setup/e2e-testing.md`, part 8. Expected result: part 9 of that guide.

## 1. New case

| Field | Type this |
|---|---|
| MSME legal name | Manual test 02 (synthetic) |
| PO reference | PO-CA-2026-0006 |
| Order value | 4,55,00,000 |
| Customer due date | 15 May 2027 |
| Requested amount | 2,00,00,000 |
| Documents | leave empty |

Press **Create case**. The case opens on the Documents tab.

## 2. Case data (Documents tab → Case data → **Fill in** on each section → **Save**)

### Customer order

| Field | Type this |
|---|---|
| Purchase order number | PO-CA-2026-0006 |
| Customer name | Customer Synthetic 06 |
| Order value | 4,55,00,000 |
| Order date | 2026-11-11 |
| Delivery weeks | 4, 7, 10 |
| Customer pays within (days) | 45 |
| Advance paid by the customer (%) | 0 |
| Business size (MSME class) | Small |
| Investment in plant and machinery | 6,00,00,000 |
| Annual turnover | 57,00,00,000 |
| Home state | Maharashtra |

### Opening cash and credit lines

| Field | Type this |
|---|---|
| Plan starts on | 2026-11-16 |
| Cash in hand and in bank | 19,11,000 |
| Minimum cash to keep at all times | 15,00,000 |

Existing credit lines:

| Lender | Type | Limit sanctioned | Amount used |
|---|---|---|---|
| Existing Banker (synthetic) | Term loan | 17,00,000 | 17,00,000 |
| Existing Banker (synthetic) | Overdraft | 47,00,000 | 17,00,000 |

Confirmed extra funds: none (leave empty)

### The five tables

| Section | Rows | Sheet in manual-entry.xlsx |
|---|---|---|
| Weekly costs | 156 | 4 Weekly costs |
| Expected receipts | 5 | 5 Expected receipts |
| Customer invoices due | 4 | 6 Customer invoices due |
| Supplier bills | 5 | 7 Supplier bills |
| Stock movement | 26 | 8 Stock movement |

For each: open the sheet, select the rows (with or without the header), copy, then in the section press **Paste rows from Excel**, paste, **Add these rows**, check, **Save**.

## 3. Lender offers (Documents tab → **Add an offer from the lender's PDFs**)

Pick each offer letter from `lender-pdfs/`. With the model off the form is empty: type the values below. Then pick the KFS PDF and the schedule of charges PDF, type the schedule rows (**Add a charge**), tick **I checked every field above against the lender's PDF**, press **Save this offer**. Repeat for each offer.

### OF-06-A: Falgu Merchant Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Falgu Merchant Bank (synthetic) |
| Loan amount | 1,93,00,000 |
| Interest rate (% a year) | 9.75 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 12 |
| Moratorium (months) | 3 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 22,32,502 |
| Offer date | 2026-11-13 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-03-18 |
| Insurance premium (if any) | 2,64,410 |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 0% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Commercial bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 2.23 | Yes |
| Annual review fee | Yearly | % of the loan | 0.25 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 2.23% of the loan amount + GST |
| Annual review fee | Yearly | 0.25% of the loan amount + GST |

### OF-06-B: Aravali Commercial Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Aravali Commercial Bank (synthetic) |
| Loan amount | 1,93,00,000 |
| Interest rate (% a year) | 11.45 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 24 |
| Moratorium (months) | 5 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 11,15,472 |
| Offer date | 2026-11-12 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-05-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | 0.85 |
| Prepayment terms | 0% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Commercial bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.99 | Yes |
| Documentation charges | Upfront | Fixed amount (₹) | 15,000 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.99% of the loan amount + GST |
| Documentation charges | Upfront | ₹15,000 + GST |
| Stamp duty and documentation handling | Upfront | ₹18,000 + GST |

### OF-06-C: Brahmaputra Industrial Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Brahmaputra Industrial Bank (synthetic) |
| Loan amount | 1,93,00,000 |
| Interest rate (% a year) | 11.25 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 24 |
| Moratorium (months) | 6 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 11,70,241 |
| Offer date | 2026-11-12 |
| Disbursal date | 2027-02-01 |
| First repayment date | 2027-09-01 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 2% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Commercial bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.8 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.8% of the loan amount + GST |

Faster alternative for offers: pick the nine files in `lender-files/` under **Add all the documents at once** instead of typing them. Both give the same comparison.
