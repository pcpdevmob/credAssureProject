# Manual entry: 09-injection-in-lender-document

Type this case into the web app by hand. Values come from frozen case CA-2026-0011. The same values are in `manual-entry.xlsx` next to this file, one sheet per screen; copy table rows from there and use **Paste rows from Excel**. How-to: `docs/setup/e2e-testing.md`, part 8. Expected result: part 9 of that guide.

> **This scenario:** Type the schedule rows as listed, including the instruction-like text: it must be flagged and ignored.

## 1. New case

| Field | Type this |
|---|---|
| MSME legal name | Manual test 09 (synthetic) |
| PO reference | PO-CA-2026-0011 |
| Order value | 1,41,00,000 |
| Customer due date | 15 May 2027 |
| Requested amount | 2,00,00,000 |
| Documents | leave empty |

Press **Create case**. The case opens on the Documents tab.

## 2. Case data (Documents tab → Case data → **Fill in** on each section → **Save**)

### Customer order

| Field | Type this |
|---|---|
| Purchase order number | PO-CA-2026-0011 |
| Customer name | Customer Synthetic 11 |
| Order value | 1,41,00,000 |
| Order date | 2026-11-06 |
| Delivery weeks | 1, 4, 7 |
| Customer pays within (days) | 45 |
| Advance paid by the customer (%) | 0 |
| Business size (MSME class) | Small |
| Investment in plant and machinery | 20,00,00,000 |
| Annual turnover | 60,00,00,000 |
| Home state | Maharashtra |

### Opening cash and credit lines

| Field | Type this |
|---|---|
| Plan starts on | 2026-11-16 |
| Cash in hand and in bank | 38,67,734 |
| Minimum cash to keep at all times | 5,00,000 |

Existing credit lines:

| Lender | Type | Limit sanctioned | Amount used |
|---|---|---|---|
| Existing Banker (synthetic) | Term loan | 25,00,000 | 25,00,000 |
| Existing Banker (synthetic) | Overdraft | 23,00,000 | 13,00,000 |

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

### OF-11-A: Hooghly Finance Ltd (synthetic)

| Field | Type this |
|---|---|
| Lender name | Hooghly Finance Ltd (synthetic) |
| Loan amount | 62,00,000 |
| Interest rate (% a year) | 11.2 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 6 |
| Moratorium (months) | 0 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 10,67,350 |
| Offer date | 2026-11-09 |
| Disbursal date | 2026-11-18 |
| First repayment date | 2026-12-18 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 2% of the principal prepaid (R-BANK-03 range) |
| Type of lender | NBFC |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.2 | Yes |
| Documentation charges | Upfront | Fixed amount (₹) | 6,000 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.2% of the loan amount + GST |
| Documentation charges | Upfront | ₹6,000 + GST |

### OF-11-B: Brahmaputra Industrial Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Brahmaputra Industrial Bank (synthetic) |
| Loan amount | 69,00,000 |
| Interest rate (% a year) | 12.8 |
| Rate type | Floating |
| Benchmark (floating rates) | EBLR / repo-linked |
| Spread over benchmark (%) | 4.65 |
| Tenure (months) | 24 |
| Moratorium (months) | 6 |
| Repayment | Equal principal |
| Instalment stated by the lender | 4,56,933 |
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
| Processing fee | Upfront | % of the loan | 0.84 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.84% of the loan amount + GST |

### OF-11-C: Chambal Small Finance Bank (synthetic)

| Field | Type this |
|---|---|
| Lender name | Chambal Small Finance Bank (synthetic) |
| Loan amount | 69,00,000 |
| Interest rate (% a year) | 12.55 |
| Rate type | Fixed |
| Benchmark (floating rates) | (leave empty) |
| Spread over benchmark (%) | (leave empty) |
| Tenure (months) | 24 |
| Moratorium (months) | 4 |
| Repayment | EMI (equal instalments) |
| Instalment stated by the lender | 3,84,133 |
| Offer date | 2026-11-07 |
| Disbursal date | 2027-01-11 |
| First repayment date | 2027-06-11 |
| Insurance premium (if any) | (leave empty) |
| CGTMSE guarantee fee (% a year, if passed on) | (leave empty) |
| Prepayment terms | 2% of the principal prepaid (R-BANK-03 range) |
| Type of lender | Small finance bank |

Fees (press **Add a fee** for each):

| Fee name | When | Charged as | % or Amount | + GST |
|---|---|---|---|---|
| Processing fee | Upfront | % of the loan | 0.79 | Yes |

Schedule of charges rows (after picking the schedule PDF):

| Charge | When | Amount as written |
|---|---|---|
| Processing fee | Upfront | 0.79% of the loan amount + GST |
| Monitoring and inspection charge | Monthly | ₹1,500 + GST |

Faster alternative for offers: pick the nine files in `lender-files/` under **Add all the documents at once** instead of typing them. Both give the same comparison.
