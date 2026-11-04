# ADR 0010 — Rounding policy

Status: Accepted · 2026-11-05 · Scope #8 · BR-05

## Decision
Money inside engines is `decimal.Decimal` with context precision 34 and `ROUND_HALF_UP`. There is no `float` on a money, rate, or IRR path in `packages/`.

- `to_paise` / `from_paise` convert at 100 paise to the rupee, half-up. Later SQLite storage uses integer paise.
- `format_inr` is display only. It uses Indian grouping (`₹1,42,00,000`). A whole rupee omits paise; a fraction shows two digits, half-up.
- `round_up_to_lakh` ceilings to the next ₹1,00,000. An exact multiple stays. A negative amount raises. The working-capital recommendation uses this after the exact formula, in Phase 4.

Rates stay Decimal fractions (`0.12` is 12%). Display is a separate function.

## Consequences
Known-answer tests compare exact Decimal values, not formatted strings, except where the assertion is about display. APR display rounding stays with the loan-cost engine (ADR 0012): the exact EMI is priced, and the displayed instalment is rounded only for output.
