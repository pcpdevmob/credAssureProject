"""S18 data-correction intents (DATA_SPEC §8.1) and S20 header-variant case files (§8.3).

Hand-written by the team (L5). S20 variants copy rows from three base cases and only rename,
reorder or add headers; ``expected_mapping.json`` is what code must accept after it validates the
model's proposed mapping (``wc_header_map v1``). An ambiguous or missing required field is never
guessed.
"""

import csv
from typing import Any

from .common import OUT, write_csv, write_json, write_jsonl

INTENTS = [
    (
        "CA-2026-0001",
        "The minimum buffer should be ₹12 lakh, not ₹10 lakh.",
        "opening_position",
        "min_cash_buffer",
        "working_capital",
    ),
    (
        "CA-2026-0002",
        "Milestone 2 will now arrive in week 14, I've updated receipts.",
        "receipts",
        "week",
        "working_capital",
    ),
    (
        "CA-2026-0003",
        "Uploading a corrected receipts file, two rows were unconfirmed.",
        "receipts",
        "confirmed",
        "working_capital",
    ),
    (
        "CA-2026-0004",
        "Opening cash is wrong, finance closed the books at a different figure.",
        "opening_position",
        "opening_cash",
        "working_capital",
    ),
    (
        "CA-2026-0005",
        "Our overdraft sanction went up last week; the new limit letter is attached.",
        "opening_position",
        "credit_lines",
        "working_capital",
    ),
    (
        "CA-2026-0006",
        "Supplier bill BILL-06-003 is due in week 9, not week 7.",
        "payables",
        "due_week",
        "working_capital",
    ),
    (
        "CA-2026-0007",
        "Invoice INV-07-002 is expected two weeks later than shown.",
        "receivables",
        "expected_week",
        "working_capital",
    ),
    (
        "CA-2026-0013",
        "Here is the opening position with the missing buffer filled in.",
        "opening_position",
        "min_cash_buffer",
        "working_capital",
    ),
    (
        "CA-2026-0014",
        "Fixed the duplicate invoice ID in the receivables upload.",
        "receivables",
        "invoice_id",
        "working_capital",
    ),
    (
        "CA-2026-0001",
        "Lender B sent a revised offer with the correct tenure, re-uploading it.",
        "offer",
        "tenure_months",
        "lendwise",
    ),
    (
        "CA-2026-0005",
        "The offer from lender A was missing its tenure; corrected file attached.",
        "offer",
        "tenure_months",
        "lendwise",
    ),
    (
        "CA-2026-0009",
        "Lender B's instalment in our record was a typo, uploading the right offer.",
        "offer",
        "stated_instalment",
        "lendwise",
    ),
    ("CA-2026-0002", "Some numbers look off.", None, None, None),
    ("CA-2026-0006", "Please fix the file I sent yesterday.", None, None, None),
    ("CA-2026-0010", "Can you update it to the new value?", None, None, None),
]

# (variant, base case, file, header map {new header: schema field or None}, expected status)
VARIANTS: list[tuple[str, str, str, dict[str, str | None], str]] = [
    (
        "HV-01",
        "CA-2026-0001",
        "costs.csv",
        {"Wk": "week", "Category": "category", "Amt": "amount"},
        "GO",
    ),
    (
        "HV-02",
        "CA-2026-0001",
        "costs.csv",
        {"amount": "amount", "category": "category", "week": "week"},
        "GO",
    ),
    (
        "HV-03",
        "CA-2026-0001",
        "receipts.csv",
        {"Week No": "week", "Source": "source", "Rashi": "amount", "Confirmed?": "confirmed"},
        "GO",
    ),
    (
        "HV-04",
        "CA-2026-0002",
        "costs.csv",
        {"week": "week", "category": "category", "amount": "amount", "remarks": None},
        "GO",
    ),
    (
        "HV-05",
        "CA-2026-0002",
        "payables.csv",
        {
            "Bill No": "bill_id",
            "Vendor": "supplier",
            "Amt": "amount",
            "Bill Wk": "bill_week",
            "Due Wk": "due_week",
            "MSME": "msme_supplier",
        },
        "GO",
    ),
    (
        "HV-06",
        "CA-2026-0002",
        "receivables.csv",
        {
            "Inv No": "invoice_id",
            "Party": "customer",
            "Amount (INR)": "amount",
            "Due Week": "due_week",
            "Expected Week": "expected_week",
        },
        "GO",
    ),
    (
        "HV-07",
        "CA-2026-0003",
        "costs.csv",
        {"Hafta": "week", "Head": "category", "Kharcha": "amount"},
        "GO",
    ),
    (
        "HV-08",
        "CA-2026-0003",
        "receivables.csv",
        {
            "Invoice": "invoice_id",
            "Customer": "customer",
            "Amount": "amount",
            "Week": None,
            "Expected": "expected_week",
        },
        "NEEDS_INPUT",
    ),
    (
        "HV-09",
        "CA-2026-0003",
        "costs.csv",
        {"Week": "week", "Category": "category", "Notes": None},
        "WC_MISSING_FIELD",
    ),
    (
        "HV-10",
        "CA-2026-0001",
        "inventory.csv",
        {
            "Wk": "week",
            "Opening": "opening_value",
            "Bought": "purchases",
            "Used": "consumption",
            "Closing": "closing_value",
        },
        "GO",
    ),
]


def _variant(
    vid: str, case_id: str, name: str, mapping: dict[str, str | None], status: str
) -> None:
    with (OUT / "cases" / case_id / name).open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    headers = list(mapping)
    out_rows = []
    for row in rows:
        if vid == "HV-08":  # "Week" stands for due_week; "Expected" for expected_week
            values = [
                row["invoice_id"],
                row["customer"],
                row["amount"],
                row["due_week"],
                row["expected_week"],
            ]
        elif vid == "HV-09":  # no amount column at all
            values = [row["week"], row["category"], "see ledger"]
        else:
            values = ["" if field is None else row[field] for field in mapping.values()]
            if vid == "HV-04":
                values[-1] = "ok"
        out_rows.append(values)
    base = OUT / "header_variants" / vid
    write_csv(base / name, headers, out_rows)
    expected: dict[str, Any] = {
        "variant_id": vid,
        "base_case": case_id,
        "file": name,
        "mapping": mapping,
        "expected_status": status,
    }
    if vid == "HV-08":
        expected["ambiguous"] = {"Week": ["due_week", "expected_week"]}
    if vid == "HV-09":
        expected["missing_field"] = "amount"
    write_json(base / "expected_mapping.json", expected)


def generate() -> list[dict[str, str]]:
    write_jsonl(
        OUT / "intents" / "data_correction.jsonl",
        [
            {
                "id": f"S18-{i:03d}",
                "case_id": case_id,
                "message": message,
                "expected_intent": "data_correction",
                "expected_file_kind": kind,
                "expected_field": field,
                "expected_reopen_stage": stage,
                "expected_clarification": stage is None,
            }
            for i, (case_id, message, kind, field, stage) in enumerate(INTENTS, start=1)
        ],
    )
    for variant in VARIANTS:
        _variant(*variant)
    return [{"id": v[0], "dataset": "S20 header variants", "plant": v[4].lower()} for v in VARIANTS]
