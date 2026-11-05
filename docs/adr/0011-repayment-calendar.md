# ADR 0011: Repayment date to week mapping

Status: Accepted · 2026-11-05 · Phase 4 · Scope #7 · LW-09/10

## Decision
- **Week numbering:** week 1 starts on the Monday after `AS_OF_DATE` (2026-11-16 by default), and the horizon is
  `FORECAST_WEEKS` (26).
- **Mapping dates to weeks:** a date maps to week `(date − week1).days // 7 + 1`. Payments outside weeks 1..26 do not
  affect the affordability overlay.
- **Monthly due dates:** payment k falls on disbursal + k calendar months, with the day capped at 28, so every month
  has the date (ADR 0021).
- **Holidays:** no shifting for bank holidays in core. The RBI NI Act holiday matrix (R-CAL-01) is optional and stays
  off, because a one- or two-day shift rarely changes the week. If it is ever turned on, it shifts a due date to the
  next working day, and both gold and the engines must apply it.

## Consequences
`credassure.engines.calendar` implements this; the gold uses the same rule independently.
