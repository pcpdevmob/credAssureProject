"""Shared helpers: seeded randomness, byte-stable writers, Indian amount text.

Every generator draws from ``rng(name)`` so adding a generator never shifts another's
stream. Writers sort keys, use ``\\n`` and never write a timestamp, so the same seed
gives the same bytes (Phase 2 acceptance).
"""

import csv
import io
import json
import os
import random
import re
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[5]
OUT = Path(os.environ.get("CREDASSURE_DATA_OUT", REPO / "data" / "frozen" / "v1"))
REFERENCE = REPO / "data" / "reference"

SEED = int(os.environ.get("CREDASSURE_SEED", "20261026"))
AS_OF_DATE = date.fromisoformat(os.environ.get("AS_OF_DATE", "2026-11-15"))
# Week 1 starts on the Monday after AS_OF_DATE (2026-11-16 by default).
WEEK1 = AS_OF_DATE + timedelta(days=(7 - AS_OF_DATE.weekday()) % 7 or 7)
WEEKS = 26
UA_PRODUCT = "CredAssure-capstone"  # robots.txt rules are matched on this token (ADR 0020)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL = re.compile(r"^https?://[^\s()]+$")


def _setting(name: str, pattern: re.Pattern[str], what: str) -> str | None:
    value = os.environ.get(name, "").strip()
    if value and not pattern.match(value):
        raise SystemExit(f"{name} is set but is not {what}; fix it or leave it empty (ADR 0020).")
    return value or None


def user_agent() -> str:
    """ADR 0020 User-Agent. Contact is optional: CORPUS_CONTACT_EMAIL wins, then CORPUS_CONTACT_URL,
    else the bare product string. A value that is set but malformed stops the run."""
    base = f"{UA_PRODUCT}/1.0 (IIT KGP academic project"
    if email := _setting("CORPUS_CONTACT_EMAIL", _EMAIL, "an email address"):
        return f"{base}; contact: {email})"
    if url := _setting("CORPUS_CONTACT_URL", _URL, "an http(s) URL"):
        return f"{base}; +{url})"
    return f"{base})"


LAKH = 100_000
CRORE = 10_000_000


def rng(name: str) -> random.Random:
    """A stream per generator, derived from the global seed (not for security)."""
    return random.Random(f"{SEED}:{name}")  # noqa: S311  # nosec B311


def week_start(week: int) -> date:
    return WEEK1 + timedelta(weeks=week - 1)


def add_months(day: date, months: int) -> date:
    month0 = day.month - 1 + months
    year, month = day.year + month0 // 12, month0 % 12 + 1
    return date(year, month, min(day.day, 28))


def round_to(amount: int, step: int = 100) -> int:
    """Round a drawn whole-rupee amount half-up to a step (no float, BR-05)."""
    return (amount + step // 2) // step * step


def pct_of(amount: int, basis_points: int) -> int:
    """``amount * basis_points / 10,000``, rounded half-up to ₹1 (integers only)."""
    return (amount * basis_points + 5_000) // 10_000


def _default(value: object) -> str:
    if isinstance(value, Decimal | date):
        return str(value)
    raise TypeError(f"not serialisable: {type(value).__name__}")


def dumps_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, default=_default) + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, obj: Any) -> None:
    write_text(path, dumps_json(obj))


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    write_text(
        path,
        "".join(
            json.dumps(r, sort_keys=True, ensure_ascii=False, default=_default) + "\n" for r in rows
        ),
    )


def write_yaml(path: Path, obj: Any) -> None:
    write_text(path, yaml.safe_dump(obj, sort_keys=True, allow_unicode=True, width=100))


def write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
    buf = io.StringIO()
    out = csv.writer(buf, lineterminator="\n")
    out.writerow(header)
    out.writerows(rows)
    write_text(path, buf.getvalue())


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _indian_group(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    pairs = [head[max(i - 2, 0) : i] for i in range(len(head), 0, -2)]
    return ",".join(reversed(pairs)) + "," + tail


def amount_text(amount: int, style: str) -> str:
    """CSV text for a whole-rupee amount: ``plain`` 1420000, ``grouped`` 14,20,000,
    ``lakh`` 14.2 lakh (only when exact to ₹1,000, else grouped)."""
    if style == "plain":
        return str(amount)
    if style == "lakh" and amount % 1000 == 0 and amount >= LAKH:
        value = format(Decimal(amount) / LAKH, "f").rstrip("0").rstrip(".")
        return f"{value} lakh"
    return _indian_group(str(amount))
