"""S03 MSME cases (DATA_SPEC §2): 15 cases x 7 files.

Parameters and sources:
- Enterprise class bands from S.O. 1364(E) (R-MSME-02, RESOURCES D3/D4): Small = investment
  up to ₹25 cr and turnover up to ₹100 cr; Medium = up to ₹125 cr / ₹500 cr. 14 Small, 1 Medium.
- MSE supplier payables fall due within 45 days (6 weeks) of the bill (R-MSME-01 s.15,
  R-TAX-01, D5), except one planted case.
- Cost shares, payment terms 30-60 days, advance 0-20%: team assumption S-WC-01.

Cash-flow conventions the generator designs to (Phase 3 gold and Phase 4 engine must match):
- Week t runs from week_start(t); 26 weeks. Cumulative cash at the end of week t =
  opening_cash + inflows - outflows summed over weeks 1..t.
- Inflows: confirmed receipts in their week (unconfirmed are excluded, WC-05) and receivables
  in their ``expected_week`` (not ``due_week``). Outflows: every cost row, and payables in
  their ``due_week``. Rows dated after week 26 fall outside the horizon. ``inventory.csv`` is
  information only: its purchases equal the components cost of the same week.
- Peak shortfall = -(lowest cumulative cash) when it is below zero. Need = max(0, peak +
  buffer - undrawn credit lines - confirmed mitigations), rounded up to ₹1 lakh (BRD §8.4).
- Confirmed mitigations offset the need only; they are not cash-table inflows (no double count).
- Affordability (LW-09) treats undrawn limits and mitigations as available cash on top of the
  cash table, adds the amount received at disbursal and subtracts every borrower payment.

Each case is built backwards from a designed peak shortfall, so the need bands are exact. The
generator never computes a gold answer; ``evaluation/gold`` recomputes from the files.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any

from .common import (
    CRORE,
    LAKH,
    OUT,
    WEEK1,
    WEEKS,
    amount_text,
    pct_of,
    rng,
    round_to,
    write_csv,
    write_json,
)

CATEGORY_BP = [  # share of a week's cost, basis points (S-WC-01)
    ("components", 5500),
    ("labour", 1500),
    ("testing", 500),
    ("packaging", 500),
    ("logistics", 500),
]


@dataclass(frozen=True)
class Spec:
    no: int
    need: int  # designed recommendation (₹, multiple of 1 lakh)
    buffer: int
    undrawn: int
    mitigation: int
    peak_week: int
    plants: tuple[str, ...]
    gap: int = -1  # amount below `need` before the lakh round-up; -1 = draw one
    peak: int = 0  # set only where the peak is fixed directly
    order_value: int = 0
    advance_bp: int = -1
    enterprise_class: str = "small"
    indian_formats: bool = False

    @property
    def case_id(self) -> str:
        return f"CA-2026-{self.no:04d}"


SPECS = [
    Spec(
        1,
        142 * LAKH,
        10 * LAKH,
        30 * LAKH,
        0,
        9,
        ("director_route", "demo_case"),
        gap=0,
        peak=162 * LAKH,
        order_value=320 * LAKH,
        advance_bp=1000,
    ),
    Spec(2, 110 * LAKH, 8 * LAKH, 20 * LAKH, 0, 8, ("director_route",), indian_formats=True),
    Spec(3, 95 * LAKH, 10 * LAKH, 0, 0, 10, ("director_route", "mse_payable_over_45d")),
    Spec(4, 125 * LAKH, 12 * LAKH, 25 * LAKH, 15 * LAKH, 11, ("director_route", "mitigation")),
    Spec(5, 148 * LAKH, 10 * LAKH, 40 * LAKH, 0, 9, ("director_route",)),
    Spec(6, 175 * LAKH, 15 * LAKH, 30 * LAKH, 0, 10, ("vp_route",), indian_formats=True),
    Spec(7, 210 * LAKH, 15 * LAKH, 20 * LAKH, 20 * LAKH, 12, ("vp_route", "mitigation")),
    Spec(
        8,
        160 * LAKH,
        12 * LAKH,
        25 * LAKH,
        0,
        9,
        ("vp_route", "medium_enterprise"),
        enterprise_class="medium",
    ),
    Spec(9, 260 * LAKH, 20 * LAKH, 50 * LAKH, 0, 11, ("vp_route",)),
    Spec(10, 150 * LAKH, 10 * LAKH, 30 * LAKH, 0, 10, ("boundary_exactly_1_5_cr",), gap=62_600),
    Spec(11, 62 * LAKH, 5 * LAKH, 10 * LAKH, 0, 7, ("need_far_below_2_cr",), indian_formats=True),
    Spec(12, 78 * LAKH, 6 * LAKH, 15 * LAKH, 10 * LAKH, 8, ("need_far_below_2_cr", "mitigation")),
    Spec(13, 120 * LAKH, 10 * LAKH, 20 * LAKH, 0, 9, ("missing_min_cash_buffer",)),
    Spec(
        14,
        105 * LAKH,
        8 * LAKH,
        15 * LAKH,
        0,
        8,
        ("conflict_receipts_vs_order", "duplicate_invoice_id"),
    ),
    Spec(15, 0, 10 * LAKH, 60 * LAKH, 0, 7, ("need_zero",), peak=40 * LAKH),
]


@dataclass
class Flows:
    receipts: list[tuple[int, str, int, bool]] = field(default_factory=list)
    costs: dict[tuple[int, str], int] = field(default_factory=dict)
    receivables: list[dict[str, Any]] = field(default_factory=list)
    payables: list[dict[str, Any]] = field(default_factory=list)

    def net(self, week: int) -> int:
        inflow = sum(a for w, _, a, ok in self.receipts if w == week and ok)
        inflow += sum(x["amount"] for x in self.receivables if x["expected_week"] == week)
        outflow = sum(a for (w, _), a in self.costs.items() if w == week)
        outflow += sum(x["amount"] for x in self.payables if x["due_week"] == week)
        return int(inflow - outflow)

    def add_cost(self, week: int, category: str, amount: int) -> None:
        self.costs[(week, category)] = self.costs.get((week, category), 0) + amount


def _peak(spec: Spec, gap: int) -> int:
    return spec.peak or spec.need - spec.buffer + spec.undrawn + spec.mitigation - gap


def _order(spec: Spec, r: Any, peak: int) -> dict[str, Any]:
    value = spec.order_value or round_to(peak * r.randint(19, 24) // 10, LAKH)
    advance_bp = spec.advance_bp if spec.advance_bp >= 0 else r.choice([0, 500, 1000, 1500, 2000])
    terms = r.choice([30, 45, 60])
    lag = (terms + 6) // 7
    first = max(1, spec.peak_week + 1 - lag)
    if spec.enterprise_class == "medium":
        investment, turnover = 60 * CRORE, 300 * CRORE
    else:
        investment = r.randint(3, 20) * CRORE
        turnover = r.randint(15, 90) * CRORE
    return {
        "schema_version": "1.0",
        "order_ref": f"PO-{spec.case_id}",
        "customer_name": f"Customer Synthetic {spec.no:02d}",
        "order_value": value,
        "currency": "INR",
        "po_date": WEEK1 - timedelta(days=r.randint(3, 12)),
        "delivery_weeks": [first, first + 3, first + 6],
        "payment_terms_days": terms,
        "advance_pct": str(Decimal(advance_bp) / 10_000),
        "enterprise_class": spec.enterprise_class,
        "investment": investment,
        "turnover": turnover,
        "home_state": "IN-MH",  # ADR 0019: Maharashtra is the synthetic MSME home state
        "_lag": lag,
        "_advance": pct_of(value, advance_bp),
    }


def _flows(spec: Spec, r: Any, order: dict[str, Any], peak: int) -> tuple[Flows, int]:
    """Weekly rows whose cumulative cash bottoms out at exactly -peak in ``peak_week``."""
    w, value, advance = spec.peak_week, order["order_value"], order["_advance"]
    f = Flows()
    if advance:
        f.receipts.append((1, "order_advance", advance, True))
    rest = value - advance
    parts = [round_to(rest * 30 // 100, 1000), round_to(rest * 40 // 100, 1000)]
    parts.append(rest - sum(parts))
    for week, part in zip(order["delivery_weeks"], parts, strict=True):
        f.receipts.append((week + order["_lag"], "order_milestone", part, True))
    for _ in range(2):  # WC-05 trap: excluded because unconfirmed
        f.receipts.append(
            (
                r.randint(2, w - 1),
                "other_customer",
                round_to(r.randint(5 * LAKH, 15 * LAKH), 1000),
                False,
            )
        )

    opening_target = round_to(r.randint(15 * LAKH, 40 * LAKH), 1000)
    pre = (peak + opening_target + advance) // w
    for week in range(1, WEEKS + 1):
        total = (
            round_to(r.randint(pre * 8 // 10, pre * 12 // 10))
            if week <= w
            else round_to(r.randint(value // 100, value * 2 // 100))
        )
        spent = 0
        for category, bp in CATEGORY_BP:
            amount = round_to(pct_of(total, bp))
            f.add_cost(week, category, amount)
            spent += amount
        f.add_cost(week, "overheads", total - spent)

    for i in range(4):
        due = r.randint(2, 24)
        f.receivables.append(
            {
                "invoice_id": f"INV-{spec.no:02d}-{i + 1:03d}",
                "customer": f"Other Customer {i + 1}",
                "amount": round_to(r.randint(3 * LAKH, 10 * LAKH), 1000),
                "due_week": due,
                "expected_week": due + r.randint(0, 2),
            }
        )
    for i in range(5):
        msme = i % 2 == 0
        bill = r.randint(1, 20)
        days = r.randint(2, 6) if msme else r.randint(4, 10)
        if msme and i == 0 and "mse_payable_over_45d" in spec.plants:
            days = 8  # D5 plant: due 8 weeks after the bill
        f.payables.append(
            {
                "bill_id": f"BILL-{spec.no:02d}-{i + 1:03d}",
                "supplier": f"Supplier Synthetic {i + 1}",
                "amount": round_to(r.randint(2 * LAKH, 8 * LAKH), 1000),
                "bill_week": bill,
                "due_week": bill + days,
                "msme_supplier": msme,
            }
        )

    # Every week from 2 to the peak loses cash, so nothing before the peak is lower.
    for week in range(2, w + 1):
        net = f.net(week)
        if net >= 0:
            f.add_cost(week, "components", net + round_to(r.randint(LAKH, 3 * LAKH), 1000))
    # After the peak, the running gain stays positive, so nothing after it is as low.
    running, extra = 0, 0
    for week in range(w + 1, WEEKS + 1):
        running += f.net(week)
        if running <= 0:
            extra += 1
            top_up = -running + round_to(r.randint(LAKH, 3 * LAKH), 1000)
            f.receivables.append(
                {
                    "invoice_id": f"INV-{spec.no:02d}-{100 + extra:03d}",
                    "customer": "Other Customer X",
                    "amount": top_up,
                    "due_week": week,
                    "expected_week": week,
                }
            )
            running += top_up
    deficit = -sum(f.net(week) for week in range(1, w + 1))
    floor = peak + round_to(r.randint(10 * LAKH, 30 * LAKH), 1000)
    if deficit < floor:
        f.add_cost(w, "components", floor - deficit)
        deficit = floor
    return f, deficit - peak  # opening cash that lands the trough on -peak


def _inventory(spec: Spec, r: Any, f: Flows) -> list[list[object]]:
    rows: list[list[object]] = []
    opening = round_to(r.randint(15 * LAKH, 40 * LAKH), 1000)
    for week in range(1, WEEKS + 1):
        purchases = f.costs[(week, "components")]
        consumption = min(opening + purchases, purchases * r.randint(85, 110) // 100)
        closing = opening + purchases - consumption
        rows.append([week, opening, purchases, consumption, closing])
        opening = closing
    return rows


def _style(spec: Spec, r: Any) -> str:
    return r.choice(["plain", "grouped", "lakh"]) if spec.indian_formats else "plain"


def generate_case(spec: Spec) -> dict[str, Any]:
    r = rng(f"case:{spec.no}")
    gap = spec.gap if spec.gap >= 0 else r.randint(0, LAKH - 1)
    peak = _peak(spec, gap)
    order = _order(spec, r, peak)
    flows, opening_cash = _flows(spec, r, order, peak)
    base = OUT / "cases" / spec.case_id

    receipts = sorted(flows.receipts)
    if "conflict_receipts_vs_order" in spec.plants:
        i = next(k for k, x in enumerate(receipts) if x[1] == "order_milestone")
        week, source, amount, ok = receipts[i]
        receipts[i] = (week, source, amount + 2 * LAKH, ok)  # milestones no longer sum to the order
    receivables = flows.receivables
    if "duplicate_invoice_id" in spec.plants:
        receivables[-1] = {**receivables[-1], "invoice_id": receivables[0]["invoice_id"]}

    drawn = round_to(r.randint(10 * LAKH, 30 * LAKH), LAKH)
    credit_lines = [
        {
            "lender": "Existing Banker (synthetic)",
            "type": "term_loan",
            "sanctioned": drawn,
            "drawn": drawn,
        }
    ]
    if spec.undrawn:
        od_drawn = round_to(r.randint(5 * LAKH, 20 * LAKH), LAKH)
        credit_lines.append(
            {
                "lender": "Existing Banker (synthetic)",
                "type": "overdraft",
                "sanctioned": spec.undrawn + od_drawn,
                "drawn": od_drawn,
            }
        )
    opening: dict[str, Any] = {
        "schema_version": "1.0",
        "as_of_week_start": WEEK1,
        "opening_cash": opening_cash,
        "min_cash_buffer": spec.buffer,
        "credit_lines": credit_lines,
        "confirmed_mitigations": (
            [
                {
                    "type": "promoter_infusion",
                    "amount": spec.mitigation,
                    "week": 3,
                    "evidence_ref": f"doc:{spec.case_id}-MIT-1",
                }
            ]
            if spec.mitigation
            else []
        ),
    }
    if "missing_min_cash_buffer" in spec.plants:
        del opening["min_cash_buffer"]

    write_json(base / "order.json", {k: v for k, v in order.items() if not k.startswith("_")})
    write_json(base / "opening_position.json", opening)
    write_csv(
        base / "costs.csv",
        ["week", "category", "amount"],
        [[w, c, amount_text(a, _style(spec, r))] for (w, c), a in sorted(flows.costs.items())],
    )
    write_csv(
        base / "receipts.csv",
        ["week", "source", "amount", "confirmed"],
        [[w, s, amount_text(a, _style(spec, r)), str(ok).lower()] for w, s, a, ok in receipts],
    )
    write_csv(
        base / "receivables.csv",
        ["invoice_id", "customer", "amount", "due_week", "expected_week"],
        [
            [
                x["invoice_id"],
                x["customer"],
                amount_text(x["amount"], _style(spec, r)),
                x["due_week"],
                x["expected_week"],
            ]
            for x in receivables
        ],
    )
    write_csv(
        base / "payables.csv",
        ["bill_id", "supplier", "amount", "bill_week", "due_week", "msme_supplier"],
        [
            [
                x["bill_id"],
                x["supplier"],
                amount_text(x["amount"], _style(spec, r)),
                x["bill_week"],
                x["due_week"],
                str(x["msme_supplier"]).lower(),
            ]
            for x in flows.payables
        ],
    )
    write_csv(
        base / "inventory.csv",
        ["week", "opening_value", "purchases", "consumption", "closing_value"],
        _inventory(spec, r, flows),
    )
    return {
        "case_id": spec.case_id,
        "design_need": None if "missing_min_cash_buffer" in spec.plants else spec.need,
        "expected_gate": "NEEDS_INPUT"
        if {"missing_min_cash_buffer", "conflict_receipts_vs_order"} & set(spec.plants)
        else "GO",
        "design_peak_shortfall": peak,
        "design_peak_week": spec.peak_week,
        "po_date": order["po_date"],
        "order_value": order["order_value"],
        "enterprise_class": spec.enterprise_class,
        "plants": list(spec.plants),
    }


def generate() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    designs = [generate_case(s) for s in SPECS]
    plants = [
        {"id": d["case_id"], "dataset": "S03 cases", "plant": p}
        for d in designs
        for p in d["plants"]
    ]
    return designs, plants
