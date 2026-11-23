# Preparer

## Create a case
Open **New case**. Type amounts the way you write them: `₹2,00,00,000`, `2,00,00,000/-`, `200 lakh` or `2 crore` all
work. The amount the system read appears under each field before you submit. If it says "Not a valid amount", fix the
text. The requested amount is only an input. The funding need is calculated from your cash-flow files.

## Upload
**Documents** has three ways in; all of them are checked the same way.
- **Excel:** download the blank template (or the filled-in example), fill in the sheets you have, and upload the
  workbook. It becomes the same case data. If anything is wrong, nothing is imported and each problem is listed by
  sheet, row and column. Sheets left empty are skipped.
- **Forms:** each of the seven sections (customer order, opening cash and credit lines, weekly costs, expected receipts,
  customer invoices, supplier bills, stock movement) opens as a form or table. Type amounts as `1,42,00,000` or
  `1.42 crore`, and paste rows copied from Excel.
- **Files:** upload a section's JSON or CSV file directly.

Lender offers (JSON, or the Excel `offers` sheet) and their KFS documents and schedules of charges (Markdown) go in
**Documents from lenders**. You can also add an offer from the lender's **PDFs**: pick the offer letter and the AI
suggests each figure, showing the words it found it in. Check every field against the PDF, correct anything wrong, add
the Key Facts Statement and schedule of charges PDFs, tick that you checked, and save. Only PDFs with selectable text can
be read (not scans), and bank statements are not read. Text that looks like an instruction is flagged and ignored, because documents are data.
To author test cases from the command line, see [case-authoring.md](case-authoring.md).

An offer whose terms cannot be priced is shown as **NOT RANKED** with the reason: for example a loan amount or
interest rate of zero, a rate typed as 12.5 instead of 12.5%, a moratorium as long as the tenure, a negative fee,
insurance added to the loan (financed) or an unusual guarantee-fee basis. Correct the offer and run the case again; the
other offers are still compared.

## Run
On **Workflow**, press **Run**. Stages run in a fixed order: readiness, funding need, lender comparison, verification,
then routing. **Live progress** shows each stage's result as it finishes.

## Questions
If a stage needs data, the case stops with one question, for example a missing minimum cash buffer. Correct it in the form
in the question card and press **Continue**. Only the blocked stage runs again. Stages that already
passed are kept.

## Ask CredAssure
The **Ask CredAssure** tab, and the **Ask CredAssure** button on every page, answer questions about using
CredAssure, rules, policies and this case, and cite their sources ([ask-credassure.md](ask-credassure.md)). Open a citation
to read the passage itself, with its document, section, effective date, legal basis and a link to the source. Some
sources (Acts) are shown as a short excerpt of up to 600 characters; the link has the rest. If CredAssure cannot find a verified source it says "I can't verify that
from the available sources", which is not an error. It does not predict approval, give legal or tax advice, accept offers,
or reveal other cases. Do not type personal identifiers; they are redacted. If the language model is switched off the tab
says so, and gates, calculations, routing and approval still work.
