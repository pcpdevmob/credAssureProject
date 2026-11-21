# ADR 0040 — Excel workbook import for case data; PDF stays out of scope

Status: Accepted, PDF section amended by ADR 0041 (owner decision 2026-11-20: "user should be able to upload Excel … and the system should convert it to
the needed CSV or JSON"; Excel now, PDF later) · Date: 2026-11-20 · Amends BRD Q-08 and §4.3 (uploads), ADR 0003
(uploads row) · Requirements UI-02, API-01, BR-15, NFR-07

## Context
The operator is a non-technical finance person. Case data had to be uploaded as seven JSON/CSV files (BRD Q-08: "JSON and
CSV only"). Progress 9.2 added web forms that build those files. People still keep this data in Excel. The team already
has an Excel template generated from the upload schemas (`data/templates/case_template.xlsx`) and a converter that
checks every file with the upload's own `validate_file` (`scripts/case_xlsx.py`), but only on the command line.

## Decision
1. `POST /v1/cases/{id}/workbook` (case preparer only, same lock and run checks as a file upload) takes the template as a
   `.xlsx`. `credassure.gateway.workbook.convert` (moved from the script, shared by it) turns the sheets into exactly the
   files a person could upload (`order.json`, `costs.csv`, …, `offers/<id>.v<n>.json`). Each file is then stored through
   `store_upload`, the single path every upload takes (validation, PII refusal, injection scan, audit `FILE_UPLOADED`).
   **The stored records are the same as an upload, so no stage, agent, engine or evaluation changes.**
2. All or nothing: any error and nothing is stored. Errors name the sheet, Excel row and column.
3. Sheets left empty are skipped (a person can send only what they have); a workbook with no filled case sheet is refused.
4. `GET /v1/templates/case.xlsx` serves the template: blank by default (headers, types, dropdowns), or `example=true`
   with the demo case filled in.
5. Untrusted input: 2 MB cap (`MAX_UPLOAD_BYTES`), zip inspected before parsing (≤ 500 entries, ≤ 40 MB uncompressed),
   openpyxl reads XML through defusedxml (now a gateway dependency), read-only mode without external links, formulas
   kept as "=…" text and refused by the upload check (never evaluated), ≤ 5,000 rows per sheet.
6. Key Facts Statements stay Markdown files from the lender (free text; BR-15).

## PDF: not now
A PDF has no reliable table structure. Turning one into case data needs either a fixed fill-in PDF form or the model
reading the PDF and a person confirming the fields. The second adds model calls to data entry and could move the
evaluation; both are more than the freeze (24 Nov) allows. Stated as a limitation in the report; candidate design after
27 Nov: model drafts the form fields from the PDF text (spotlighted, data only), the person reviews them in the web form,
code validates, and nothing is stored without that review.

## Consequences
- One more way in, same gate: every check that applies to an uploaded file applies to an imported sheet.
- `scripts/case_xlsx.py convert` keeps its strict mode (every sheet required) for authoring test cases.
- Tests: `apps/gateway/tests/test_adr0040_workbook.py` (same stored records as single uploads, errors by sheet/row/column
  and nothing stored, partial workbook, formulas and PAN refused, zip bomb, preparer only, template download).
