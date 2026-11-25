# ruff: noqa: E501  (screen labels and help text are kept whole so they can be compared with the web forms)
"""Manual-entry sheets for the test pack: what to type into each web form, scenario by scenario.

    uv run python scripts/manual_entry_pack.py          # writes data/test-pack/<scenario>/manual-entry.{xlsx,md}

Teammates who create a case by hand (New case, then Documents -> each "Case data" form, then the
lender-PDF review form) need the values in the same order and with the same labels as the screens.
Every value is copied from the frozen case files (data/frozen/v1/cases/<case>/) and the test pack's
lender files; nothing is calculated or invented here (BRD §10). Money is written as typed on screen
(Indian grouping), percentages as 10 for 10%, choices by their on-screen label. Table sheets have the
on-screen column labels as their header, so rows can be copied and pasted with "Paste rows from Excel"
(the form skips a pasted header row). Deterministic: the same inputs give the same files.
"""

from __future__ import annotations

import csv
import io
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data" / "test-pack"
FROZEN = ROOT / "data" / "frozen" / "v1" / "cases"
REQUESTED = "2,00,00,000"  # every scenario's indicative request (the ₹2 crore of BRD §1)
DUE = "2027-05-15"

# Labels and choices exactly as apps/web/src/lib/caseForms.ts and lib/offerPdf.ts show them.
CHOICE = {
    "enterprise_class": {"micro": "Micro", "small": "Small", "medium": "Medium"},
    "home_state": {
        "IN-MH": "Maharashtra",
        "IN-GJ": "Gujarat",
        "IN-KA": "Karnataka",
        "IN-TN": "Tamil Nadu",
        "IN-UP": "Uttar Pradesh",
        "IN-TS": "Telangana",
        "IN-DL": "Delhi",
        "IN-HR": "Haryana",
        "IN-WB": "West Bengal",
    },
    "type": {"overdraft": "Overdraft", "cash_credit": "Cash credit", "term_loan": "Term loan"},
    "mitigation": {
        "promoter_infusion": "Owner / promoter funds",
        "asset_sale": "Asset sale",
        "other": "Other",
    },
    "category": {
        "components": "Components",
        "labour": "Labour",
        "testing": "Testing",
        "packaging": "Packaging",
        "logistics": "Logistics",
        "overheads": "Overheads",
    },
    "source": {
        "order_advance": "Order advance",
        "order_milestone": "Order milestone payment",
        "other_customer": "Another customer",
    },
    "bool": {"true": "Yes", "false": "No"},
    "rate_type": {"fixed": "Fixed", "floating": "Floating"},
    "benchmark": {"EBLR": "EBLR / repo-linked", "MCLR": "MCLR"},
    "method": {"emi": "EMI (equal instalments)", "equal_principal": "Equal principal"},
    "lender_type": {
        "commercial_bank": "Commercial bank",
        "nbfc": "NBFC",
        "sfb": "Small finance bank",
        "coop_bank": "Co-operative bank",
    },
    "timing": {"upfront": "Upfront", "monthly": "Monthly", "annual": "Yearly"},
}
ORDER = [
    ("order_ref", "Purchase order number", "text"),
    ("customer_name", "Customer name", "text"),
    ("order_value", "Order value", "money"),
    ("po_date", "Order date", "date"),
    ("delivery_weeks", "Delivery weeks", "list"),
    ("payment_terms_days", "Customer pays within (days)", "text"),
    ("advance_pct", "Advance paid by the customer (%)", "percent"),
    ("enterprise_class", "Business size (MSME class)", "enterprise_class"),
    ("investment", "Investment in plant and machinery", "money"),
    ("turnover", "Annual turnover", "money"),
    ("home_state", "Home state", "home_state"),
]
OPENING = [
    ("as_of_week_start", "Plan starts on", "date"),
    ("opening_cash", "Cash in hand and in bank", "money"),
    ("min_cash_buffer", "Minimum cash to keep at all times", "money"),
]
CREDIT = [
    ("lender", "Lender", "text"),
    ("type", "Type", "type"),
    ("sanctioned", "Limit sanctioned", "money"),
    ("drawn", "Amount used", "money"),
]
MITIGATION = [
    ("type", "What it is", "mitigation"),
    ("amount", "Amount", "money"),
    ("week", "Arrives in week", "text"),
    ("evidence_ref", "Evidence reference", "text"),
]
TABLES = [  # (file, sheet / form title, columns)
    (
        "costs",
        "Weekly costs",
        [
            ("week", "Week", "text"),
            ("category", "Cost type", "category"),
            ("amount", "Amount", "money"),
        ],
    ),
    (
        "receipts",
        "Expected receipts",
        [
            ("week", "Week", "text"),
            ("source", "From", "source"),
            ("amount", "Amount", "money"),
            ("confirmed", "Confirmed?", "bool"),
        ],
    ),
    (
        "receivables",
        "Customer invoices due",
        [
            ("invoice_id", "Invoice number", "text"),
            ("customer", "Customer", "text"),
            ("amount", "Amount", "money"),
            ("due_week", "Due in week", "text"),
            ("expected_week", "Expected in week", "text"),
        ],
    ),
    (
        "payables",
        "Supplier bills",
        [
            ("bill_id", "Bill number", "text"),
            ("supplier", "Supplier", "text"),
            ("amount", "Amount", "money"),
            ("bill_week", "Billed in week", "text"),
            ("due_week", "Due in week", "text"),
            ("msme_supplier", "Supplier is a micro or small business?", "bool"),
        ],
    ),
    (
        "inventory",
        "Stock movement",
        [
            ("week", "Week", "text"),
            ("opening_value", "Opening stock", "money"),
            ("purchases", "Bought", "money"),
            ("consumption", "Used", "money"),
            ("closing_value", "Closing stock", "money"),
        ],
    ),
]
OFFER = [
    ("lender_name", "Lender name", "text"),
    ("principal", "Loan amount", "money"),
    ("annual_rate", "Interest rate (% a year)", "percent"),
    ("rate_type", "Rate type", "rate_type"),
    ("benchmark", "Benchmark (floating rates)", "benchmark"),
    ("spread", "Spread over benchmark (%)", "percent"),
    ("tenure_months", "Tenure (months)", "text"),
    ("moratorium_months", "Moratorium (months)", "text"),
    ("repayment", "Repayment", "method"),
    ("stated_instalment", "Instalment stated by the lender", "money"),
    ("issue_date", "Offer date", "date"),
    ("disbursal_date", "Disbursal date", "date"),
    ("first_repayment_date", "First repayment date", "date"),
    ("insurance", "Insurance premium (if any)", "money"),
    ("guarantee", "CGTMSE guarantee fee (% a year, if passed on)", "percent"),
    ("prepayment_terms", "Prepayment terms", "text"),
    ("lender_type", "Type of lender", "lender_type"),
]
SCENARIO_NOTES = {
    "04-missing-schedule-question": "Add offers A and C with all three PDFs. For offer OF-02-B add the offer letter and the KFS but no schedule of charges: the lender comparison then asks for it. Answer with the PDF in answer-the-question/.",
    "05-missing-case-data-question": "Leave **Minimum cash to keep at all times** empty: the funding check stops and asks for it. Answer on the question card (for example 10 lakh).",
    "06-conflicting-case-data": "Type the receipts and invoices exactly as listed, conflicts included: the funding check stops on them. Then fix the receipts as the question says.",
    "09-injection-in-lender-document": "Type the schedule rows as listed, including the instruction-like text: it must be flagged and ignored.",
    "10-wrong-case-document": "Offer OF-01-A's KFS names another case number: pick it as it is; it is kept and flagged for review.",
}


def money(value: Any) -> str:
    """Rupees as typed on screen. Plain numbers get Indian grouping; text such as '142 lakh' is kept."""
    text = str(value).strip()
    if not re.fullmatch(r"\d+(\.\d+)?", text):
        return text
    whole, _, frac = text.partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    out = ",".join([*groups, tail]) if groups else tail
    frac = frac.rstrip("0")
    return out + (f".{frac}" if frac else "")


def percent(value: Any) -> str:
    """'0.1045' → '10.45' (a decimal shift, no float)."""
    shown = format((Decimal(str(value)) * 100).normalize(), "f")
    return shown


def show(value: Any, kind: str) -> str:
    if value is None or value == "":
        return ""
    if kind == "money":
        return money(value)
    if kind == "percent":
        return percent(value)
    if kind == "list":
        return ", ".join(str(v) for v in value)
    if kind in CHOICE:
        return CHOICE[kind].get(str(value).lower() if kind == "bool" else str(value), str(value))
    return str(value)


def rows_of(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))


def schedule_rows(md: str) -> list[tuple[str, str, str]]:
    rows = []
    for line in md.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if (
            line.startswith("|")
            and len(cells) == 3
            and cells[0] not in ("Charge", "---")
            and not set(cells[0]) <= {"-"}
        ):
            rows.append((cells[0], CHOICE["timing"].get(cells[1], cells[1]), cells[2]))
    return rows


def offer_values(o: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, _, kind in OFFER:
        v = o.get(key)
        if key == "repayment":
            v = (v or {}).get("method")
        elif key == "insurance":
            v = (v or {}).get("premium")
        elif key == "guarantee":
            v = (v or {}).get("annual_fee_pct")
        out[key] = show(v, kind)
    if not out["moratorium_months"]:
        out["moratorium_months"] = "0"
    return out


def offer_ticks(o: dict[str, Any]) -> list[str]:
    ticks = []
    if (o.get("insurance") or {}).get("financed"):
        ticks.append("Tick: The insurance premium is added to the loan")
    if (o.get("guarantee") or {}).get("gst_applicable"):
        ticks.append("Tick: GST is charged on the guarantee fee")
    if o.get("fees") == []:
        ticks.append("Tick: The letter says there are no fees")
    if "fees" not in o:
        ticks.append(
            "Leave the fees empty and do NOT tick 'no fees': the letter does not state them (a missing term)"
        )
    if "tenure_months" not in o:
        ticks.append("Leave Tenure empty: the letter does not state it (a missing term)")
    return ticks


def fee_rows(o: dict[str, Any]) -> list[list[str]]:
    rows = []
    for f in o.get("fees") or []:
        pct = f["basis"] == "pct_of_principal"
        rows.append(
            [
                f["name"],
                CHOICE["timing"].get(f["timing"], f["timing"]),
                "% of the loan" if pct else "Fixed amount (₹)",
                percent(f["value"]) if pct else money(f["value"]),
                "Yes" if f.get("gst_applicable") else "No",
            ]
        )
    return rows


HEAD = Font(bold=True, color="FFFFFF")
FILL = PatternFill("solid", fgColor="1F3A5F")
NOTE = Font(italic=True, color="555555")


def header(ws: Worksheet, labels: list[str]) -> None:
    ws.append(labels)
    for cell in ws[ws.max_row]:
        cell.font, cell.fill = HEAD, FILL
    ws.freeze_panes = f"A{ws.max_row + 1}"


def widths(ws: Worksheet) -> None:
    for col in ws.columns:
        longest = max(len(str(c.value or "")) for c in col)
        ws.column_dimensions[get_column_letter(col[0].column or 1)].width = min(
            max(12, longest + 2), 70
        )
    for row in ws.iter_rows():
        for c in row:
            c.number_format = "@"  # text: Excel must not re-format "13,38,300" or "2026-11-04"
            c.alignment = Alignment(vertical="top", wrap_text=len(str(c.value or "")) > 70)


def build(folder: Path) -> None:
    case_id = re.search(r"CA-\d{4}-\d{4}", next(folder.glob("case-data-*.xlsx")).name).group(0)  # type: ignore[union-attr]
    src = FROZEN / case_id
    order = json.loads((src / "order.json").read_text(encoding="utf-8"))
    opening = json.loads((src / "opening_position.json").read_text(encoding="utf-8"))
    offers = [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((folder / "lender-files").glob("*.json"))
    ]
    schedules = {
        p.name.removesuffix("-v1-SCH.md").removeprefix("KFS-"): p.read_text(encoding="utf-8")
        for p in sorted((folder / "lender-files").glob("*-SCH.md"))
    }

    wb = Workbook()
    ws = wb.create_sheet("1 New case")
    wb.remove(wb.worksheets[0])
    header(ws, ["Field on screen", "Type this"])
    for label, value in [
        ("MSME legal name", f"Manual test {folder.name[:2]} (synthetic)"),
        ("PO reference", order["order_ref"]),
        ("Order value", money(order["order_value"])),
        ("Customer due date", DUE),
        ("Requested amount", REQUESTED),
        ("Currency", "INR"),
        ("Documents (optional)", "Leave empty: you type the case data next"),
    ]:
        ws.append([label, value])
    widths(ws)

    ws = wb.create_sheet("2 Customer order")
    header(ws, ["Field on screen", "Type this"])
    for key, label, kind in ORDER:
        ws.append([label, show(order.get(key), kind)])
    widths(ws)

    ws = wb.create_sheet("3 Opening cash")
    header(ws, ["Field on screen", "Type this"])
    for key, label, kind in OPENING:
        ws.append([label, show(opening.get(key), kind) or "(leave empty)"])
    ws.append([])
    ws.append(["Existing credit lines: one row each (press Add row, or Paste rows from Excel)"])
    ws[ws.max_row][0].font = NOTE
    ws.append([lbl for _, lbl, _ in CREDIT])
    for cell in ws[ws.max_row]:
        cell.font, cell.fill = HEAD, FILL
    for line in opening.get("credit_lines", []):
        ws.append([show(line.get(k), kind) for k, _, kind in CREDIT])
    ws.append([])
    ws.append(
        [
            "Confirmed extra funds (optional)"
            + ("" if opening.get("confirmed_mitigations") else ": none, leave empty")
        ]
    )
    ws[ws.max_row][0].font = NOTE
    if opening.get("confirmed_mitigations"):
        ws.append([lbl for _, lbl, _ in MITIGATION])
        for m in opening["confirmed_mitigations"]:
            ws.append([show(m.get(k), kind) for k, _, kind in MITIGATION])
    widths(ws)

    counts = {}
    for n, (name, title, cols) in enumerate(TABLES, start=4):
        ws = wb.create_sheet(f"{n} {title}"[:31])
        header(ws, [lbl for _, lbl, _ in cols])
        rows = rows_of(src / f"{name}.csv")
        counts[title] = len(rows)
        for r in rows:
            ws.append([show(r.get(k), kind) for k, _, kind in cols])
        widths(ws)

    ws = wb.create_sheet("9 Lender offers")
    header(ws, ["Field on screen", *[o["offer_id"] for o in offers]])
    values = [offer_values(o) for o in offers]
    for key, label, _ in OFFER:
        ws.append([label, *[v[key] for v in values]])
    ws.append(["Tick boxes", *["; ".join(offer_ticks(o)) or "none" for o in offers]])
    ws.append(
        [
            "PDFs to pick (lender-pdfs/)",
            *[f"{o['offer_id']}: offer letter, KFS, schedule of charges" for o in offers],
        ]
    )
    widths(ws)

    ws = wb.create_sheet("10 Offer fees")
    header(ws, ["Offer", "Fee name", "When", "Charged as", "% or Amount", "+ GST"])
    for o in offers:
        for row in fee_rows(o):
            ws.append([o["offer_id"], *row])
    widths(ws)

    ws = wb.create_sheet("11 Schedule of charges")
    header(ws, ["Offer", "Charge", "When", "Amount as written"])
    for o in offers:
        for charge in schedule_rows(schedules.get(o["offer_id"], "")):
            ws.append([o["offer_id"], *charge])
    widths(ws)
    wb.properties.creator = "CredAssure test pack"
    wb.save(folder / "manual-entry.xlsx")
    _fixed_zip_dates(folder / "manual-entry.xlsx")

    (folder / "manual-entry.md").write_text(
        markdown(folder, case_id, order, opening, offers, schedules, counts), encoding="utf-8"
    )


def _fixed_zip_dates(path: Path) -> None:
    """Same bytes on every run: fixed timestamps inside the xlsx (a zip) and in its core properties."""
    import zipfile

    data = {}
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            body = z.read(info.filename)
            if info.filename == "docProps/core.xml":
                body = re.sub(
                    rb"<dcterms:(created|modified)([^>]*)>[^<]*<",
                    rb"<dcterms:\1\2>2026-11-25T00:00:00Z<",
                    body,
                )
            data[info.filename] = body
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in data.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 25, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, body)


def md_table(head: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines)


def markdown(
    folder: Path,
    case_id: str,
    order: dict[str, Any],
    opening: dict[str, Any],
    offers: list[dict[str, Any]],
    schedules: dict[str, str],
    counts: dict[str, int],
) -> str:
    out = [
        f"# Manual entry: {folder.name}",
        "",
        f"Type this case into the web app by hand. Values come from frozen case {case_id}. The same values are in "
        "`manual-entry.xlsx` next to this file, one sheet per screen; copy table rows from there and use "
        "**Paste rows from Excel**. How-to: `docs/setup/e2e-testing.md`, part 8. Expected result: part 9 of that guide.",
        "",
    ]
    if folder.name in SCENARIO_NOTES:
        out += [f"> **This scenario:** {SCENARIO_NOTES[folder.name]}", ""]
    out += [
        "## 1. New case",
        "",
        md_table(
            ["Field", "Type this"],
            [
                ["MSME legal name", f"Manual test {folder.name[:2]} (synthetic)"],
                ["PO reference", order["order_ref"]],
                ["Order value", money(order["order_value"])],
                ["Customer due date", "15 May 2027"],
                ["Requested amount", REQUESTED],
                ["Documents", "leave empty"],
            ],
        ),
        "",
        "Press **Create case**. The case opens on the Documents tab.",
        "",
        "## 2. Case data (Documents tab → Case data → **Fill in** on each section → **Save**)",
        "",
        "### Customer order",
        "",
        md_table(
            ["Field", "Type this"], [[lbl, show(order.get(k), kind)] for k, lbl, kind in ORDER]
        ),
        "",
        "### Opening cash and credit lines",
        "",
        md_table(
            ["Field", "Type this"],
            [[lbl, show(opening.get(k), kind) or "(leave empty)"] for k, lbl, kind in OPENING],
        ),
        "",
        "Existing credit lines:",
        "",
        md_table(
            [lbl for _, lbl, _ in CREDIT],
            [
                [show(c.get(k), kind) for k, _, kind in CREDIT]
                for c in opening.get("credit_lines", [])
            ],
        ),
        "",
        "Confirmed extra funds: "
        + ("see sheet 3" if opening.get("confirmed_mitigations") else "none (leave empty)"),
        "",
        "### The five tables",
        "",
        md_table(
            ["Section", "Rows", "Sheet in manual-entry.xlsx"],
            [[t, str(counts[t]), f"{n} {t}"] for n, (_, t, _) in enumerate(TABLES, start=4)],
        ),
        "",
        "For each: open the sheet, select the rows (with or without the header), copy, then in the section press "
        "**Paste rows from Excel**, paste, **Add these rows**, check, **Save**.",
        "",
        "## 3. Lender offers (Documents tab → **Add an offer from the lender's PDFs**)",
        "",
        "Pick each offer letter from `lender-pdfs/`. With the model off the form is empty: type the values below. "
        "Then pick the KFS PDF and the schedule of charges PDF, type the schedule rows (**Add a charge**), tick "
        "**I checked every field above against the lender's PDF**, press **Save this offer**. Repeat for each offer.",
        "",
    ]
    for o in offers:
        v = offer_values(o)
        out += [
            f"### {o['offer_id']}: {o['lender_name']}",
            "",
            md_table(
                ["Field", "Type this"], [[lbl, v[k] or "(leave empty)"] for k, lbl, _ in OFFER]
            ),
            "",
        ]
        fees = fee_rows(o)
        out += [
            "Fees (press **Add a fee** for each):",
            "",
            md_table(["Fee name", "When", "Charged as", "% or Amount", "+ GST"], fees)
            if fees
            else "none",
            "",
        ]
        ticks = offer_ticks(o)
        if ticks:
            out += [*[f"- {t}" for t in ticks], ""]
        sch = schedule_rows(schedules.get(o["offer_id"], ""))
        out += [
            "Schedule of charges rows (after picking the schedule PDF):",
            "",
            md_table(["Charge", "When", "Amount as written"], [list(r) for r in sch])
            if sch
            else "no schedule in this scenario (the app asks for it)",
            "",
        ]
    out += [
        "Faster alternative for offers: pick the nine files in `lender-files/` under **Add all the documents at "
        "once** instead of typing them. Both give the same comparison.",
        "",
    ]
    return "\n".join(out)


def main() -> None:
    for folder in sorted(p for p in PACK.iterdir() if p.is_dir()):
        build(folder)
        print(f"wrote {folder.relative_to(ROOT)}/manual-entry.xlsx and .md")


if __name__ == "__main__":
    main()
