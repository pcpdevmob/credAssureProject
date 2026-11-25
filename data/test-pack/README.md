# CredAssure end-to-end test pack (synthetic)

One folder per scenario: the case data as an Excel workbook, each lender's offer letter, Key Facts Statement and
schedule of charges as PDFs (`lender-pdfs/`) and as files (`lender-files/`: offer `.json`, KFS and schedule `.md`).
`answer-the-question/` holds the document the app is expected to ask for in scenario 04.

To type a case in by hand instead of uploading files, each folder also has `manual-entry.md` (every screen in order,
field label and value to type) and `manual-entry.xlsx` (the same, one sheet per screen; table sheets use the screen's
column names, so rows can be pasted with **Paste rows from Excel**). They are written by
`uv run python scripts/manual_entry_pack.py` from the frozen case files and the lender files here; a test checks they are
current.

How to use it and what each scenario should show: [docs/setup/e2e-testing.md](../../docs/setup/e2e-testing.md).

Generated on 24 Nov 2026 from `data/frozen/v1` (read only). All companies, lenders and figures are synthetic; every
lender is simulated. Not used by any evaluation.
