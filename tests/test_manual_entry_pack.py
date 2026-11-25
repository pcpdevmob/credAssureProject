"""Manual-entry sheets in data/test-pack (25 Nov): values to type into the web forms, copied
from the frozen cases. The committed sheets must be what the script writes, every money value must
read back to the frozen figure, and each table sheet's header must be the web form's own labels."""

import csv
import importlib.util
import io
import re
import shutil
from pathlib import Path
from types import ModuleType

import openpyxl
import pytest

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data" / "test-pack"
FORMS_TS = (ROOT / "apps/web/src/lib/caseForms.ts").read_text(encoding="utf-8")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "manual_entry_pack", ROOT / "scripts" / "manual_entry_pack.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MEP = _load()
SCENARIOS = sorted(p.name for p in PACK.iterdir() if p.is_dir())


def test_money_and_percent_are_written_as_a_person_types_them() -> None:
    assert MEP.money("32000000") == "3,20,00,000"
    assert MEP.money("1000000") == "10,00,000"
    assert MEP.money("186830") == "1,86,830"
    assert MEP.money("999") == "999"
    assert MEP.money("1,06,800") == "1,06,800"  # already Indian-formatted in the frozen CSV: kept
    assert MEP.money("15000.50") == "15,000.5"
    assert MEP.percent("0.1045") == "10.45"
    assert MEP.percent("0.1") == "10"


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_committed_sheets_are_what_the_script_writes(scenario: str, tmp_path: Path) -> None:
    src = PACK / scenario
    copy = tmp_path / scenario
    shutil.copytree(src, copy, ignore=shutil.ignore_patterns("manual-entry.*"))
    MEP.build(copy)
    for name in ("manual-entry.xlsx", "manual-entry.md"):
        stale = f"{scenario}/{name} is stale: run scripts/manual_entry_pack.py"
        assert (copy / name).read_bytes() == (src / name).read_bytes(), stale


def _digits(text: str) -> int:
    return int(re.sub(r"[^\d]", "", text))


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_table_sheets_match_the_frozen_rows_and_the_web_labels(scenario: str) -> None:
    wb = openpyxl.load_workbook(PACK / scenario / "manual-entry.xlsx")
    case_id = re.search(r"CA-\d{4}-\d{4}", next((PACK / scenario).glob("case-data-*.xlsx")).name)
    assert case_id
    frozen = MEP.FROZEN / case_id.group(0)
    for n, (name, title, cols) in enumerate(MEP.TABLES, start=4):
        rows = list(wb[f"{n} {title}"[:31]].iter_rows(values_only=True))
        assert list(rows[0]) == [label for _, label, _ in cols]
        for _, label, _ in cols:
            assert f"label: '{label}'" in FORMS_TS, f"{label!r} is not a label in caseForms.ts"
        source = list(csv.DictReader(io.StringIO((frozen / f"{name}.csv").read_text("utf-8"))))
        assert len(rows) - 1 == len(source)
        for got, want in zip(rows[1:], source, strict=True):
            for value, (key, _, kind) in zip(got, cols, strict=True):
                if kind == "money" and re.fullmatch(r"[\d,]+", str(want[key])):
                    assert _digits(str(value)) == _digits(want[key])
