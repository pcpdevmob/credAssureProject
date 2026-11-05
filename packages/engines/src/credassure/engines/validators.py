"""Case-file validation (WC-01/02, RESOURCES D5). Pure.

Blockers stop the funding stage; warnings never do. Checks: required fields; currency; week
range; order receipts vs order value; duplicate invoice and bill IDs; MSE supplier payables
due more than 45 days (6 weeks) after the bill (warning only).
"""

from collections import Counter
from decimal import Decimal, localcontext

from credassure.core.blockers import BlockerCode
from credassure.core.money import MONEY
from credassure.core.results import Blocker

from .cashflow import CaseFiles, money

REQUIRED_ORDER = (
    "order_ref",
    "order_value",
    "po_date",
    "delivery_weeks",
    "payment_terms_days",
    "enterprise_class",
)
REQUIRED_OPENING = ("as_of_week_start", "opening_cash", "min_cash_buffer", "credit_lines")
MSE_MAX_WEEKS = 6  # 45 days (MSMED Act s.15, R-MSME-01)


def _missing(name: str, field: str) -> Blocker:
    return Blocker(
        code=BlockerCode.WC_MISSING_FIELD,
        field=f"{name}.{field}",
        message=f"{field} is missing from {name}.",
        next_action=f"Upload {name} with {field} filled in.",
    )


def validate(files: CaseFiles, weeks: int = 26) -> tuple[list[Blocker], list[Blocker]]:
    """(blockers, warnings)."""
    blockers = [_missing("order", f) for f in REQUIRED_ORDER if f not in files.order]
    blockers += [
        _missing("opening_position", f) for f in REQUIRED_OPENING if f not in files.opening
    ]
    if files.order.get("currency", "INR") != "INR":
        blockers.append(
            Blocker(
                code=BlockerCode.WC_UNIT_OR_CURRENCY,
                field="order.currency",
                message="Only INR amounts are supported.",
            )
        )
    for name, rows, key, upper in (
        ("costs", files.costs, "week", weeks * 4),
        ("receipts", files.receipts, "week", weeks * 4),
        ("receivables", files.receivables, "expected_week", None),
        ("payables", files.payables, "due_week", None),
    ):
        if any(not 1 <= int(r[key]) <= (upper or int(r[key])) for r in rows):
            blockers.append(
                Blocker(
                    code=BlockerCode.WC_DATE_OUT_OF_RANGE,
                    field=f"{name}.{key}",
                    message=f"A {name} row has a week outside the forecast.",
                )
            )
    if "order_value" in files.order:
        with localcontext(MONEY):
            order_receipts = sum(
                (
                    money(r["amount"])
                    for r in files.receipts
                    if r["source"] in {"order_advance", "order_milestone"}
                    and str(r["confirmed"]).lower() == "true"
                ),
                Decimal(0),
            )
            if abs(order_receipts - money(files.order["order_value"])) > 1:
                blockers.append(
                    Blocker(
                        code=BlockerCode.WC_CONFLICT_TOTALS,
                        field="receipts",
                        message="Order receipts do not add up to the order value.",
                        next_action="Correct the milestone schedule or the order value.",
                    )
                )
    for name, rows, key in (
        ("receivables", files.receivables, "invoice_id"),
        ("payables", files.payables, "bill_id"),
    ):
        dupes = sorted(k for k, n in Counter(str(r[key]) for r in rows).items() if n > 1)
        if dupes:
            blockers.append(
                Blocker(
                    code=BlockerCode.WC_DUPLICATE_ID,
                    field=f"{name}.{key}",
                    message=f"Duplicate {key}: {', '.join(dupes)}.",
                )
            )
    warnings = [
        Blocker(
            code=BlockerCode.WC_MSE_PAYABLE_OVER_45D,
            field="payables.due_week",
            message=f"Bill {r['bill_id']} to an MSE supplier is due over 45 days after the bill.",
        )
        for r in files.payables
        if str(r.get("msme_supplier")).lower() == "true"
        and r.get("bill_week") not in (None, "")
        and int(r["due_week"]) - int(r["bill_week"]) > MSE_MAX_WEEKS
    ]
    return blockers, warnings
