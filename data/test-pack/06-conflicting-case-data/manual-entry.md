# Manual entry: 06-conflicting-case-data

Type this case into the web app by hand. Values come from frozen case CA-2026-0014. The same values are in `manual-entry.xlsx` next to this file, one sheet per screen; copy table rows from there and use **Paste rows from Excel**. How-to: `docs/setup/e2e-testing.md`, part 8. Expected result: part 9 of that guide.

> **This scenario:** Type the receipts and invoices exactly as listed, conflicts included: the funding check stops on them. Then fix the receipts as the question says.

## 1. New case

| Field | Type this |
|---|---|
| MSME legal name | Manual test 06 (synthetic) |
| PO reference | PO-CA-2026-0014 |
| Order value | 2,56,00,000 |
| Customer due date | 15 May 2027 |
| Requested amount | 2,00,00,000 |
| Documents | leave empty |

Press **Create case**. The case opens on the Documents tab.

## 2. Case data (Documents tab → Case data → **Fill in** on each section → **Save**)

### Customer order

| Field | Type this |
|---|---|
| Purchase order number | PO-CA-2026-0014 |
| Customer name | Customer Synthetic 14 |
| Order value | 2,56,00,000 |
| Order date | 2026-11-08 |
| Delivery weeks | 2, 5, 8 |
| Customer pays within (days) | 45 |
| Advance paid by the customer (%) | 20 |
| Business size (MSME class) | Small |
| Investment in plant and machinery | 8,00,00,000 |
| Annual turnover | 39,00,00,000 |
| Home state | Maharashtra |

### Opening cash and credit lines

| Field | Type this |
|---|---|
| Plan starts on | 2026-11-16 |
| Cash in hand and in bank | 28,53,854 |
| Minimum cash to keep at all times | 8,00,000 |

Existing credit lines:

| Lender | Type | Limit sanctioned | Amount used |
|---|---|---|---|
| Existing Banker (synthetic) | Term loan | 24,00,000 | 24,00,000 |
| Existing Banker (synthetic) | Overdraft | 20,00,000 | 5,00,000 |

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

### OF-14-A: Chambal Small Finance Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Chambal Small Finance Bank (synthetic) |
| Loan amount | 1,16,00,000 |
| Interest rate (% a year) | 10.05 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 12 |
| Moratorium (months) | 3 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 13,43,461 |
| Offer date | 2026-11-11 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-03-18 |
| Insurance premium (if any) | 1,71,680 |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 1% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Small finance bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 2.09 | Yes |
| Annual review fee | Yearly | % of the loan | 0.25 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 2.09% of the loan amount + GST |
| Annual review fee | Yearly | 0.25% of the loan amount + GST |

### OF-14-B: Brahmaputra Industrial Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Brahmaputra Industrial Bank (synthetic) |
| Loan amount | 1,05,00,000 |
| Interest rate (% a year) | 10.3 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 6 |
| Moratorium (months) | 0 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 18,02,947 |
| Offer date | 2026-11-10 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2026-12-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 1% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Commercial bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.2 | Yes |
| Documentation charges | Upfront | Fixed amount (₹) | 13,000 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.2% of the loan amount + GST |
| Documentation charges | Upfront | ₹13,000 + GST |

### OF-14-C: Indravati Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Indravati Bank (synthetic) |
| Loan amount | 1,16,00,000 |
| Interest rate (% a year) | 11.85 |
| Rate type | Floating |
| Benchmark (floating rates) | EBLR / repo-linked |
| Spread over benchmark (%) | 3.7 |
| Tenure (months) | 18 |
| Moratorium (months) | 4 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 8,91,244 |
| Offer date | 2026-11-15 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2027-04-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 0% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Commercial bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.8 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.8% of the loan amount + GST |
| Stamp duty and documentation handling | Upfront | ₹18,000 + GST |

Faster alternative for offers: pick the nine files in `lender-files/` under **Add all the documents at once** instead of typing them. Both give the same comparison.
