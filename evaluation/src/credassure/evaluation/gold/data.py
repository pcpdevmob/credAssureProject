"""Read the frozen synthetic data for gold (Phase 3). Independent of the engines and the generators.

Gold never imports ``credassure.engines`` or ``credassure.datagen`` and never reads ``_design/``
(the generator's design intent): it recomputes everything from the files a user would upload.
"""

import csv
import json
from datetime import date, timedelta
from functools import cache
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[5]
DATA = REPO / "data" / "frozen" / "v1"
REFERENCE = REPO / "data" / "reference"
AS_OF = date(2026, 11, 15)
WEEK1 = date(2026, 11, 16)  # Monday after AS_OF_DATE (DATA_SPEC §2)
WEEKS = 26
LAKH = 100_000
INDICATIVE = 20_000_000  # the ₹2 crore request (BR-01)


def amount(text: str) -> float:
    """CSV amounts as written: plain, Indian-grouped or 'x lakh'."""
    text = text.strip()
    if text.endswith("lakh"):
        return float(text[:-4].strip()) * LAKH
    return float(text.replace(",", ""))


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def case_ids() -> list[str]:
    return sorted(p.name for p in (DATA / "cases").glob("CA-*"))


@cache
def case(case_id: str) -> dict[str, Any]:
    base = DATA / "cases" / case_id
    return {
        "order": json.loads((base / "order.json").read_text(encoding="utf-8")),
        "opening": json.loads((base / "opening_position.json").read_text(encoding="utf-8")),
        "costs": rows(base / "costs.csv"),
        "receipts": rows(base / "receipts.csv"),
        "receivables": rows(base / "receivables.csv"),
        "payables": rows(base / "payables.csv"),
    }


@cache
def offers(case_id: str) -> list[dict[str, Any]]:
    folder = DATA / "offers" / case_id
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]


def kfs_text(doc_id: str) -> str:
    path = DATA / "kfs" / f"{doc_id}.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@cache
def gst_rate() -> float:
    return float(yaml.safe_load((REFERENCE / "gst.yaml").read_text(encoding="utf-8"))["rate"])


@cache
def hr_profiles() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads(
        (DATA / "hr" / "profiles.json").read_text(encoding="utf-8")
    )
    return data


@cache
def lender_scripts() -> dict[str, dict[str, Any]]:
    return {
        p.stem: yaml.safe_load(p.read_text(encoding="utf-8"))
        for p in (DATA / "lender_scripts").glob("*.yaml")
    }


def week_of(day: date) -> int:
    return (day - WEEK1).days // 7 + 1


def add_months(day: date, months: int) -> date:
    """Calendar months; the day is capped at 28 (the offer convention in DATA_SPEC §3)."""
    month0 = day.month - 1 + months
    return date(day.year + month0 // 12, month0 % 12 + 1, min(day.day, 28))


def parse_date(text: str) -> date:
    return date.fromisoformat(str(text))


def week_start(week: int) -> date:
    return WEEK1 + timedelta(weeks=week - 1)
