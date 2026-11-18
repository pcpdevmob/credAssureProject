# Creating test data: step by step

This folder holds everything needed to create a new test case without touching the frozen data:

| Path | What it is |
|---|---|
| `case_template.xlsx` | Excel template, one tab per file. Fill it in and convert it (route A). |
| `sample_case/` | A complete, valid case to copy from (route B): the demo case CA-2026-0016, from frozen CA-2026-0001. |
| `sample_case/order.json`, `opening_position.json` | The two JSON case files |
| `sample_case/costs.csv` … `inventory.csv` | The five CSV case files |
| `sample_case/offers/*.json` | Three lender offers (one file per offer version) |
| `sample_case/kfs/*.md` | Each offer's Key Facts Statement and schedule of charges |

`make case-template` regenerates both from the live schemas. **Never edit or add files under `data/frozen/`.**

---

## Step 1: Decide what the case should test

Write down the expected outcome before you write any numbers. Examples:

| Goal | How to get it |
|---|---|
| Director approval | Recommended amount below ₹1,50,00,000 |
| VP approval | Recommended amount above ₹1,50,00,000 |
| Held at the boundary | Recommended amount exactly ₹1,50,00,000 after rounding up to the lakh |
| Paused for data | Leave out a required field, e.g. `min_cash_buffer` |
| Conflict | Confirmed order receipts that don't add up to `order_value`, or a repeated `invoice_id` |
| No loan needed | Cash never drops below the buffer |
| Hidden charge | A charge in the KFS schedule that isn't in the offer's `fees` |
| Unaffordable offer | Instalments that start before customer receipts arrive |
| Missing material term | Leave out `tenure_months`, or leave the fee schedule unstated |

Recommended amount = peak cumulative shortfall + `min_cash_buffer` − undrawn credit lines − confirmed
mitigations, never below zero, rounded **up** to ₹1 lakh. The ₹2 crore request is never the answer.

## Step 2: Pick a route

- **Route A (Excel):** copy `case_template.xlsx` and fill it in. Row 1 is the field, row 2 the type, row 3
  required or optional, and data starts on row 4. Use the dropdowns. Overwrite or delete the shaded example
  rows.
- **Route B (files):** copy `sample_case/` to `var/<your_case>/` and edit the files directly.

```bash
cp data/templates/case_template.xlsx var/my_case.xlsx          # route A
cp -R data/templates/sample_case var/my_case                    # route B
```

## Step 3: Fill in the case files

**order.json**: exactly one order.
- Required for the funding stage: `order_ref`, `order_value`, `po_date`, `delivery_weeks`,
  `payment_terms_days`, `enterprise_class`.
- Required at upload: `customer_name`, `advance_pct`, `investment`, `turnover`.
- `enterprise_class` is `micro`, `small` or `medium`. Use `small` unless you are testing the CGTMSE warning,
  because CGTMSE covers micro and small only. `home_state` defaults to `IN-MH`.

**opening_position.json**:
- Required for the funding stage: `as_of_week_start` (a Monday, `YYYY-MM-DD`), `opening_cash`,
  `min_cash_buffer`, `credit_lines`.
- Undrawn credit = `sanctioned − drawn` on each line.
- Every `confirmed_mitigations` item needs an `evidence_ref`. An offset without a source isn't used.

**CSV files**: the header row must match the field names exactly. One row per line item.

| File | Columns | Rules |
|---|---|---|
| `costs.csv` | week, category, amount | category: components, labour, testing, packaging, logistics, overheads |
| `receipts.csv` | week, source, amount, confirmed | **Confirmed `order_advance` + `order_milestone` rows must add up to `order_value` (±₹1)**. Unconfirmed rows are ignored. |
| `receivables.csv` | invoice_id, customer, amount, due_week, expected_week | `invoice_id` must be unique |
| `payables.csv` | bill_id, supplier, amount, bill_week, due_week, msme_supplier | `bill_id` must be unique. A payable to an MSME supplier due more than 6 weeks (45 days) after its bill raises a warning, not a block. |
| `inventory.csv` | week, opening_value, purchases, consumption, closing_value | |

Weeks are counted from 1. The forecast is 26 weeks.

## Step 4: Fill in the offers (optional, needed for the lender stage)

One JSON file per offer version: `offers/<offer_id>.v<version>.json`. Give each case 3 offers.

- **Ids:** `offer_id` looks like `OF-<letters, digits, ->`, `kfs_doc_id` like `KFS-<…>`, and `lender_id` is
  letters, digits and `-`. `version` runs from 1 to 99.
- **Rates and fees** are decimals: `0.1045` means 10.45% a year, and `0.0235` means 2.35% of principal.
- **`fees`:** a list means these are the fees, and `[]` means the offer has no fees. **Leaving `fees` out**
  means the fee schedule isn't stated, and the offer is flagged non-comparable.
- **Floating rate:** set `rate_type: floating`, a `benchmark` (`EBLR`; `MCLR` on a micro or small case is a
  planted anomaly) and a `spread`.
- **`stated_instalment`** is checked against the recomputed instalment, to ₹1.

**KFS documents**: each offer needs `kfs/<kfs_doc_id>.md` and usually `kfs/<kfs_doc_id>-SCH.md` (the schedule
of charges). The frontmatter must include `doc_id`, and should include `offer_id` and `case_id`. The body is
plain Markdown tables. To plant a **hidden charge**, put it in the schedule but not in the offer's `fees`; the
sample's "Legal and valuation charges" in `KFS-OF-01-A-v1-SCH.md` is one. Text in a KFS is data and is never
obeyed.

## Step 5: Keep it synthetic

Use obviously fictional names ("Customer Synthetic 01", "… (synthetic)"). **No Aadhaar, PAN or bank account
numbers**: uploads containing them are refused. Don't start text with `=`, `+`, `-` or `@` (treated as a
spreadsheet formula). Write amounts as plain digits or Indian formats (`1,42,00,000`, `142 lakh`), never
`1E+7`.

## Step 6: Validate

Route A converts and validates in one step:
```bash
make case-from-xlsx FILE=var/my_case.xlsx OUT=var/my_case
```
Errors name the tab, the Excel row and the column. If there are any errors, nothing is written.

Route B: upload is the validation, because the API returns each problem as field, row and reason. To check
locally before uploading, open the files in the Excel template (route A), or run the same check the API runs:
```bash
uv run python -c "import sys; from credassure.gateway.routers.cases import validate_file; \
print(validate_file(sys.argv[1], open(sys.argv[2]).read())[1], 'rows ok')" costs var/my_case/costs.csv
```

## Step 7: Upload and run

In the web UI: **New case**, then **Documents** (7 case files), then **Lender offers and KFS** (offer JSON,
KFS `.md`), then **Run**. Or through the API, with a preparer token in `$T`:
```bash
CID=$(curl -s -X POST localhost:8000/v1/cases -H "Authorization: Bearer $T" -H 'Content-Type: application/json' \
  -d '{"msme_name":"Test MSME","order_ref":"PO-T1","order_value_paise":3200000000,"indicative_amount_paise":2000000000,"due_date":"2027-05-15"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["case_id"])')
up() { curl -s -X POST "localhost:8000/v1/cases/$CID/files?kind=$1" -H "Authorization: Bearer $T" -F "file=@$2"; echo; }
up order var/my_case/order.json;  up opening_position var/my_case/opening_position.json
for k in costs receipts receivables payables inventory; do up $k var/my_case/$k.csv; done
for f in var/my_case/offers/*.json; do up offer "$f"; done
for f in var/my_case/kfs/*.md; do up kfs "$f"; done
curl -s -X POST localhost:8000/v1/cases/$CID/run -H "Authorization: Bearer $T"
```

## Step 8: Check the outcome

Compare the result with what you wrote down in step 1:
- `GET /v1/cases/{id}`: status, route, any question.
- `GET /v1/cases/{id}/funding`: recommended amount and its bridge.
- `GET /v1/cases/{id}/offers`: APR, flags, ranking.

If the result differs, work out the expected figure by hand before you assume the code is wrong.

## Rules

- Test data lives in `var/` (git-ignored) or a new folder. **Never** under `data/frozen/`: a hook blocks it,
  and `case-from-xlsx` refuses it.
- To add a case to the frozen eval set, follow the freeze process (`/freeze-g1`). Don't edit `v1/`.
- After a schema change, run `make case-template`. A test fails until the template and samples match.
