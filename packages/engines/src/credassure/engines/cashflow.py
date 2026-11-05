"""Weekly cash table, peak shortfall and recommended facility (WC-03..06, BR-01/02, ADR 0021).

Pure, Decimal only.

- cumulative cash at the end of week t = opening cash + confirmed receipts + receivables in
  their expected week - costs - payables in their due week; rows after the horizon are
  ignored; inventory is information only;
- peak shortfall = -(lowest cumulative cash) when below zero; peak week = the lowest week;
- need = max(0, peak + buffer - undrawn limits - mitigations with evidence arriving by the
  peak week), rounded up to ₹1 lakh; mitigations offset the need, never inflows (WC-05);
- the bridge from the indicative request sums exactly to the recommendation (WC-06).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Any

from credassure.core.money import MONEY, round_up_to_lakh

from .normaliser import parse_money


def money(value: Any) -> Decimal:
    """An amount from a file: Decimal, int or Indian-format text (₹1,42,00,000 / 142 lakh)."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return Decimal(value)
    if isinstance(value, str):
        return parse_money(value).value
    raise TypeError(f"not a money value: {value!r}")


@dataclass(frozen=True)
class CaseFiles:
    order: Mapping[str, Any]
    opening: Mapping[str, Any]
    costs: Sequence[Mapping[str, Any]]
    receipts: Sequence[Mapping[str, Any]]
    receivables: Sequence[Mapping[str, Any]]
    payables: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class CashRow:
    week: int
    inflow: Decimal
    outflow: Decimal
    cumulative: Decimal


@dataclass(frozen=True)
class CashTable:
    rows: tuple[CashRow, ...]
    peak_shortfall: Decimal
    peak_week: int
    shortfall_weeks: int

    def cumulative(self) -> list[Decimal]:
        return [r.cumulative for r in self.rows]


@dataclass(frozen=True)
class Recommendation:
    peak_shortfall: Decimal
    peak_week: int
    min_cash_buffer: Decimal
    undrawn_limits: Decimal
    mitigations: Decimal
    recommended_amount: Decimal
    bridge: tuple[tuple[str, Decimal], ...]


def _confirmed(row: Mapping[str, Any]) -> bool:
    value = row.get("confirmed")
    return value is True or str(value).strip().lower() == "true"


def cash_table(files: CaseFiles, weeks: int = 26) -> CashTable:
    inflow = [Decimal(0)] * (weeks + 1)
    outflow = [Decimal(0)] * (weeks + 1)
    with localcontext(MONEY):
        for r in files.costs:
            if 1 <= int(r["week"]) <= weeks:
                outflow[int(r["week"])] += money(r["amount"])
        for r in files.receipts:
            if _confirmed(r) and 1 <= int(r["week"]) <= weeks:
                inflow[int(r["week"])] += money(r["amount"])
        for r in files.receivables:
            if 1 <= int(r["expected_week"]) <= weeks:
                inflow[int(r["expected_week"])] += money(r["amount"])
        for r in files.payables:
            if 1 <= int(r["due_week"]) <= weeks:
                outflow[int(r["due_week"])] += money(r["amount"])
        cumulative = money(files.opening["opening_cash"])
        rows = []
        for week in range(1, weeks + 1):
            cumulative += inflow[week] - outflow[week]
            rows.append(CashRow(week, inflow[week], outflow[week], cumulative))
    lowest = min(rows, key=lambda r: (r.cumulative, r.week))
    return CashTable(
        rows=tuple(rows),
        peak_shortfall=max(Decimal(0), -lowest.cumulative),
        peak_week=lowest.week,
        shortfall_weeks=sum(1 for r in rows if r.cumulative < 0),
    )


def available_limits(
    opening: Mapping[str, Any], by_week: int | None = None
) -> tuple[Decimal, Decimal]:
    """Undrawn sanctioned limits; confirmed mitigations with evidence arriving by ``by_week``."""
    with localcontext(MONEY):
        undrawn = sum(
            (
                max(Decimal(0), money(x["sanctioned"]) - money(x["drawn"]))
                for x in opening.get("credit_lines", [])
            ),
            Decimal(0),
        )
        mitigations = sum(
            (
                money(x["amount"])
                for x in opening.get("confirmed_mitigations", [])
                if x.get("evidence_ref") and (by_week is None or int(x["week"]) <= by_week)
            ),
            Decimal(0),
        )
    return undrawn, mitigations


def recommend(files: CaseFiles, table: CashTable, *, indicative: Decimal) -> Recommendation:
    buffer = money(files.opening["min_cash_buffer"])
    undrawn, mitigations = available_limits(files.opening, by_week=table.peak_week)
    with localcontext(MONEY):
        exact = table.peak_shortfall + buffer - undrawn - mitigations
        floored = max(Decimal(0), exact)
        need = round_up_to_lakh(floored)
        bridge = (
            ("indicative_request", indicative),
            ("peak_shortfall_vs_request", table.peak_shortfall - indicative),
            ("min_cash_buffer", buffer),
            ("undrawn_credit_limits", -undrawn),
            ("confirmed_mitigations", -mitigations),
            ("floor_at_zero", floored - exact),
            ("round_up_to_lakh", need - floored),
        )
    return Recommendation(
        table.peak_shortfall, table.peak_week, buffer, undrawn, mitigations, need, bridge
    )
