# Authoring a test case in Excel

Step-by-step guide and a complete set of sample files (JSON, CSV, offers, KFS): [data/templates/README.md](../../data/templates/README.md).

In the app you do not need this conversion: on **Documents**, upload the filled workbook and it is converted and checked
the same way (ADR 0040). The steps below are for authoring test cases from the command line.

Use this to write a new MSME case and its lender offers in a spreadsheet instead of editing seven CSV/JSON files
and an offer JSON for each lender by hand.

## 1. Copy the template
`data/templates/case_template.xlsx` is generated from the same schemas the API uses for uploads. Copy it, and don't
edit the original. The shaded rows are an **example**: the main demo case CA-2026-0016 (frozen CA-2026-0001) and its
three offers. Overwrite or delete them.

| Tab | Becomes | Rows |
|---|---|---|
| order, opening_position | `order.json`, `opening_position.json` | exactly one |
| costs, receipts, receivables, payables, inventory | one CSV each | one per line |
| offers | `offers/<offer_id>.v<version>.json` | one per offer version |
| delivery_weeks, credit_lines, confirmed_mitigations, fees | list fields of the row whose `row_id` they name | any |

In every tab, row 1 is the field name, row 2 the type and row 3 whether the field is required. Data starts on row 4.
Columns with a fixed set of values have a dropdown. Dates (`YYYY-MM-DD`), true/false and id columns are formatted as
text, so Excel won't change them. Amounts can be plain digits or Indian formats (`1,42,00,000`, `142 lakh`).
Formulas are refused: type values.

Offer fees: if an offer has fee rows in **fees**, those are its fees. If it has none, set `fees_none` to `true` when
the offer states that there are no fees. Leave it blank when the fee schedule isn't stated (the audit then flags a
missing material term).

## 2. Convert and validate
```bash
make case-from-xlsx FILE=my_case.xlsx OUT=var/my_case
```
Every file is checked by the gateway's own upload check (`validate_file`), so a file that passes here also passes
upload. Errors name the tab, the Excel row and the column, for example:
```
costs: row 5, column category: Input should be 'components', 'labour', ...
credit_lines: row 4, column row_id: no opening_position row has row_id '9'
```
If any error is found, nothing is written and the exit code is 1. OUT can't be under `data/frozen/`.

## 3. Upload
Create a case and upload the files from OUT on **Documents** (or `POST /v1/cases/{id}/files?kind=...`). The KFS and
schedule-of-charges documents are free text, so they aren't in the workbook: upload each offer's `<kfs_doc_id>.md`
separately.

After a schema change, regenerate the template with `make case-template`. A test fails until you do.
