"""Phase 2 acceptance: seeded, byte-identical data v1 with the DATA_SPEC plants (BR-01, BRD §10)."""

import csv
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from credassure.core.schemas.case_files import (
    CostRow,
    InventoryRow,
    OpeningPosition,
    OrderFile,
    PayableRow,
    ReceiptRow,
    ReceivableRow,
)
from credassure.core.schemas.offer import Offer
from credassure.datagen.common import WEEK1

DATA = Path(__file__).resolve().parents[2] / "frozen" / "v1"
PLANTS = json.loads((DATA / "plants.json").read_text(encoding="utf-8"))
COUNTS = Counter((p["dataset"], p["plant"]) for p in PLANTS)


def _generate(out: Path) -> str:
    env = {**os.environ, "CREDASSURE_DATA_OUT": str(out)}
    subprocess.run(
        [sys.executable, "-m", "credassure.datagen"], env=env, check=True, capture_output=True
    )
    return (out / "SHA256SUMS").read_text(encoding="utf-8")


@pytest.mark.slow
def test_BR10_make_data_is_byte_identical_and_matches_committed(tmp_path: Path) -> None:
    first = _generate(tmp_path / "a")
    assert first == _generate(tmp_path / "b")
    assert first == (DATA / "SHA256SUMS").read_text(encoding="utf-8")


def test_ONB03_hr_plants_exact() -> None:
    expected = {
        "go": 8,
        "training_expired": 3,
        "training_missing": 2,
        "role_not_authorised": 3,
        "ack_missing_or_old": 2,
        "training_in_progress": 1,
        "expired_and_ack_missing": 1,
    }
    assert {p: n for (d, p), n in COUNTS.items() if d == "S01 HR"} == expected


def test_WC03_case_plants_match_spec() -> None:
    cases = {p: n for (d, p), n in COUNTS.items() if d == "S03 cases"}
    assert cases["director_route"] == 5
    assert cases["vp_route"] == 4
    for plant in (
        "boundary_exactly_1_5_cr",
        "missing_min_cash_buffer",
        "need_zero",
        "conflict_receipts_vs_order",
        "medium_enterprise",
        "mse_payable_over_45d",
    ):
        assert cases[plant] == 1
    assert cases["need_far_below_2_cr"] == 2


@pytest.mark.parametrize(
    ("plant", "minimum"),
    [
        ("headline", 6),
        ("unaffordable", 6),
        ("hidden", 8),
        ("mismatch", 5),
        ("eblr", 5),
        ("mclr", 2),
        ("cgtmse", 6),
        ("eligible_0", 1),
        ("eligible_1", 1),
        ("eligible_2", 1),
        ("eligible_3", 1),
    ],
)
def test_LW_offer_plant_minimums(plant: str, minimum: int) -> None:
    assert COUNTS[("S04 offers", plant)] >= minimum


def test_LW02_LW10_combined_plant_minimums() -> None:
    offers = {p: n for (d, p), n in COUNTS.items() if d == "S04 offers"}
    assert offers["missing_tenure"] + offers["missing_fees"] >= 4
    assert offers["late"] + offers["short"] >= 4


def test_KFS_and_policy_volumes() -> None:
    assert 120 <= len(list((DATA / "kfs").glob("*.md"))) <= 160
    assert 60 <= len(list((DATA / "policies").glob("*.md"))) <= 90
    assert COUNTS[("S06 KFS", "injection_text")] == 10
    assert sum(n for (d, p), n in COUNTS.items() if p.startswith("cross_case_from_")) == 5


def _amount(text: str) -> int:
    """The three styles the generator writes, parsed locally (no engine, so no shared bug)."""
    if text.endswith(" lakh"):
        whole, _, frac = text[:-5].partition(".")
        return int(whole) * 100_000 + int(frac.ljust(5, "0")) if frac else int(whole) * 100_000
    return int(text.replace(",", ""))


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.parametrize("case_dir", sorted((DATA / "cases").glob("CA-*")), ids=lambda p: p.name)
def test_WC01_case_files_match_core_schemas(case_dir: Path) -> None:
    OrderFile.model_validate_json((case_dir / "order.json").read_text(encoding="utf-8"))
    opening = json.loads((case_dir / "opening_position.json").read_text(encoding="utf-8"))
    if "min_cash_buffer" in opening:
        OpeningPosition.model_validate(opening)
    for name, model in [
        ("costs.csv", CostRow),
        ("receipts.csv", ReceiptRow),
        ("receivables.csv", ReceivableRow),
        ("payables.csv", PayableRow),
        ("inventory.csv", InventoryRow),
    ]:
        for row in _rows(case_dir / name):
            if "amount" in row:
                row["amount"] = str(_amount(row["amount"]))
            model.model_validate(row)


def _cash_path(base: Path) -> tuple[list[int], dict[str, Any]]:
    """Cumulative cash at the end of weeks 1..26 (index 0 = week 1), per cases.py."""
    opening = json.loads((base / "opening_position.json").read_text(encoding="utf-8"))
    net = [0] * 27
    for r in _rows(base / "costs.csv"):
        net[int(r["week"])] -= _amount(r["amount"])
    for r in _rows(base / "receipts.csv"):
        if r["confirmed"] == "true":
            net[int(r["week"])] += _amount(r["amount"])
    for r in _rows(base / "receivables.csv"):
        if int(r["expected_week"]) <= 26:
            net[int(r["expected_week"])] += _amount(r["amount"])
    for r in _rows(base / "payables.csv"):
        if int(r["due_week"]) <= 26:
            net[int(r["due_week"])] -= _amount(r["amount"])
    path, cum = [], opening["opening_cash"]
    for week in range(1, 27):
        cum += net[week]
        path.append(cum)
    return path, opening


def test_BR01_designed_need_reproduces_from_the_files() -> None:
    """Independent recompute of the trough (not the engine): the plant bands are real."""
    designs = json.loads((DATA / "_design" / "designs.json").read_text(encoding="utf-8"))
    for d in designs:
        path, opening = _cash_path(DATA / "cases" / d["case_id"])
        low = min(path)
        assert -low == d["design_peak_shortfall"], d["case_id"]
        assert path.index(low) + 1 == d["design_peak_week"], d["case_id"]
        if "min_cash_buffer" not in opening:
            assert d["design_need"] is None
            continue
        undrawn = sum(x["sanctioned"] - x["drawn"] for x in opening["credit_lines"])
        mitigations = sum(x["amount"] for x in opening["confirmed_mitigations"])
        need = max(0, -low + opening["min_cash_buffer"] - undrawn - mitigations)
        assert math.ceil(need / 100_000) * 100_000 == d["design_need"], d["case_id"]


def _week(day: str) -> int:
    return (date.fromisoformat(day) - WEEK1).days // 7 + 1


def _lowest_cash_with_offer(o: dict[str, Any], path: list[int], opening: dict[str, Any]) -> float:
    """LW-09 overlay (float is fine in a test): cash + available limits + loan - payments."""
    principal, rate = float(o["principal"]), float(o["annual_rate"]) / 12
    gst = 1.18
    upfront = sum(
        (float(f["value"]) * principal if f["basis"] == "pct_of_principal" else float(f["value"]))
        * (gst if f["gst_applicable"] else 1)
        for f in o["fees"]
        if f["timing"] in ("upfront", "annual")
    )
    if o["insurance"]:
        upfront += float(o["insurance"]["premium"])
    if o["guarantee"]:
        g = o["guarantee"]
        upfront += principal * float(g["annual_fee_pct"]) * (gst if g["gst_applicable"] else 1)
    pay = [0.0] * 27
    disbursal = _week(o["disbursal_date"])
    n = o["tenure_months"] - o["moratorium_months"]
    balance = principal
    for month in range(1, o["tenure_months"] + 1):
        due = date.fromisoformat(o["disbursal_date"]) + timedelta(days=round(month * 30.44))
        week = (due - WEEK1).days // 7 + 1
        interest = balance * rate
        if month <= o["moratorium_months"]:
            amount = interest
        elif o["repayment"]["method"] == "emi":
            amount = principal * rate * (1 + rate) ** n / ((1 + rate) ** n - 1)
            balance -= amount - interest
        else:
            amount = principal / n + interest
            balance -= principal / n
        if week <= 26:
            pay[week] += amount
    available = sum(x["sanctioned"] - x["drawn"] for x in opening["credit_lines"])
    available += sum(x["amount"] for x in opening["confirmed_mitigations"])
    paid, lowest = 0.0, float("inf")
    for week in range(1, 27):
        paid += pay[week]
        received = principal - upfront if week >= disbursal else 0.0
        lowest = min(lowest, path[week - 1] + available + received - paid)
    return lowest


def test_LW09_LW14_eligible_offers_fit_and_unaffordable_plants_do_not() -> None:
    """The eligible_N plants are only true if eligible offers keep cash above the buffer."""
    for case_dir in sorted((DATA / "cases").glob("CA-*")):
        path, opening = _cash_path(case_dir)
        if "min_cash_buffer" not in opening:
            continue
        for offer_path in sorted(case_dir.parent.parent.glob(f"offers/{case_dir.name}/*.v1.json")):
            o = json.loads(offer_path.read_text(encoding="utf-8"))
            tags = {p["plant"] for p in PLANTS if p["id"] == o["offer_id"]}
            if "tenure_months" not in o or "fees" not in o or tags & {"late", "short"}:
                continue
            lowest = _lowest_cash_with_offer(o, path, opening)
            if "unaffordable" in tags:
                assert lowest < opening["min_cash_buffer"], o["offer_id"]
            else:
                assert lowest >= opening["min_cash_buffer"], (o["offer_id"], lowest)


def test_WC05_D5_msme_payables_within_45_days_except_the_plant() -> None:
    late = []
    for case_dir in sorted((DATA / "cases").glob("CA-*")):
        for r in _rows(case_dir / "payables.csv"):
            if r["msme_supplier"] == "true" and int(r["due_week"]) - int(r["bill_week"]) > 6:
                late.append(case_dir.name)
    assert late == ["CA-2026-0003"]


def test_LW01_complete_offers_match_the_offer_schema() -> None:
    for path in sorted((DATA / "offers").glob("*/*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        if "tenure_months" in raw and "fees" in raw:
            Offer.model_validate(raw)


PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
AADHAAR = re.compile(r"\b[2-9][0-9]{3}\s?[0-9]{4}\s?[0-9]{4}\b")


def test_NFR07_no_pan_or_aadhaar_patterns_anywhere() -> None:
    for path in DATA.rglob("*"):
        if path.is_file() and path.suffix in {".json", ".csv", ".md", ".yaml", ".jsonl"}:
            text = path.read_text(encoding="utf-8")
            assert not PAN.search(text), path
            assert not AADHAAR.search(text), path


def test_LW04_hidden_charges_live_only_in_the_schedule() -> None:
    hidden = [p["id"] for p in PLANTS if p["dataset"] == "S04 offers" and p["plant"] == "hidden"]
    for offer_id in hidden:
        case = f"CA-2026-00{offer_id[3:5]}"
        offer = json.loads(
            (DATA / "offers" / case / f"{offer_id}.v1.json").read_text(encoding="utf-8")
        )
        schedule = (DATA / "kfs" / f"{offer['kfs_doc_id']}-SCH.md").read_text(encoding="utf-8")
        rows = [r.split("|")[1].strip() for r in schedule.splitlines() if r.startswith("| ")][1:]
        extra = set(rows) - {f["name"] for f in offer.get("fees", [])}
        assert len(extra) == 1, (offer_id, extra)
