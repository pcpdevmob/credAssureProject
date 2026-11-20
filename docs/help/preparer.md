# Preparer

## Create a case
Open **New case**. Type amounts the way you write them: `₹2,00,00,000`, `2,00,00,000/-`, `200 lakh` or `2 crore` all
work. The amount the system read appears under each field before you submit. If it says "Not a valid amount", fix the
text. The requested amount is only an input. The funding need is calculated from your cash-flow files.

## Upload
**Documents** has one slot for each of the seven case files: order and opening position (JSON), and costs, receipts,
receivables, payables and inventory (CSV). Lender offers (JSON) and their KFS documents and schedules of charges
(Markdown) go in the **Lender offers and KFS** box. If a file is rejected, each problem is listed as row, field and
reason. Fix those and upload the file again. Text that looks like an instruction is flagged and ignored, because
documents are data.

To write a new case in Excel and convert it to these files, see [case-authoring.md](case-authoring.md).

## Run
On **Workflow**, press **Run**. Stages run in a fixed order: readiness, funding need, lender comparison, verification,
then routing. **Live progress** shows each stage's result as it finishes.

## Questions
If a stage needs data, the case stops with one question, for example a missing minimum cash buffer. Upload the
corrected file in the question card and press **Resume**. Only the blocked stage runs again. Stages that already
passed are kept.

## Ask CredAssure
The **Ask CredAssure** tab, and the **Ask CredAssure** button on every page, answer questions about using
CredAssure, rules, policies and this case, and cite their sources ([ask-credassure.md](ask-credassure.md)). Open a citation
to read the passage itself, with its document, section, effective date, legal basis and a link to the source. Some
sources (Acts) are shown as a short excerpt of up to 600 characters; the link has the rest. If CredAssure cannot find a verified source it says "I can't verify that
from the available sources", which is not an error. It does not predict approval, give legal or tax advice, accept offers,
or reveal other cases. Do not type personal identifiers; they are redacted. If the language model is switched off the tab
says so, and gates, calculations, routing and approval still work.
