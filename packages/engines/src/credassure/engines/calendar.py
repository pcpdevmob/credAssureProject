"""Calendar helpers for the cash table and repayment schedules (scope #7, ADR 0011). Pure."""

from datetime import date, timedelta


def week1_start(as_of: date) -> date:
    """Week 1 starts on the Monday after ``as_of`` (a Monday as_of moves a full week on)."""
    return as_of + timedelta(days=(7 - as_of.weekday()) % 7 or 7)


def week_of(day: date, week1: date) -> int:
    return (day - week1).days // 7 + 1


def week_start(week: int, week1: date) -> date:
    return week1 + timedelta(weeks=week - 1)


def add_months(day: date, months: int) -> date:
    """Calendar months; the day is capped at 28 so every month has the date (ADR 0021)."""
    month0 = day.month - 1 + months
    return date(day.year + month0 // 12, month0 % 12 + 1, min(day.day, 28))
