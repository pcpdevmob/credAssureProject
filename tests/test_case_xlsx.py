"""scripts/case_xlsx.py: xlsx -> files round-trips the demo case, errors name tab/row/column,
frozen data is never written, and the converted files give the same API results (UI-02)."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from credassure.gateway.main import create_app
from credassure.gateway.routers.cases import validate_file
from credassure.gateway.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "data" / "frozen" / "v1"
CASE = "CA-2026-0001"
CSV_KINDS = ("costs", "receipts", "receivables", "payables", "inventory")


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


kit = _load("case_xlsx")


def _frozen_hash() -> str:
    h = hashlib.sha256()
    for p in sorted(FROZEN.rglob("*")):
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("tpl") / "case_template.xlsx"
    kit.build_template(path)
    return path


def test_committed_template_is_current(template: Path) -> None:
    """Regenerate with `make case-template` after a schema change."""
    assert kit.TEMPLATE.read_bytes() == template.read_bytes()


def test_template_layout(template: Path) -> None:
    wb = load_workbook(template)
    assert wb.sheetnames[0] == "README" and "EXAMPLE" in str(wb["README"]["A3"].value)
    expected = {*[t for t, _, _ in kit.TABS], "delivery_weeks", "credit_lines"}
    assert expected | {"confirmed_mitigations", "fees"} <= set(wb.sheetnames)
    costs = wb["costs"]
    assert [c.value for c in costs[3]][:3] == ["required"] * 3
    dropdowns = {str(dv.sqref): dv.formula1 for dv in costs.data_validations.dataValidation}
    assert any("components" in f for f in dropdowns.values())
    offers = wb["offers"]
    header = [c.value for c in offers[1]]
    assert "repayment.method" in header and kit.FEES_NONE in header
    col = header.index("disbursal_date") + 1
    assert offers.cell(kit.DATA_ROW, col).number_format == "@"  # dates stay text


def test_round_trip_matches_frozen_demo_case(template: Path, tmp_path: Path) -> None:
    before = _frozen_hash()
    assert kit.main(["convert", str(template), str(tmp_path)]) == 0
    src = FROZEN / "cases" / CASE
    for kind, ext in [("order", "json"), ("opening_position", "json")] + [
        (k, "csv") for k in CSV_KINDS
    ]:
        name = f"{kind}.{ext}"
        assert validate_file(kind, (tmp_path / name).read_text()) == validate_file(
            kind, (src / name).read_text()
        ), name
    offers = sorted((FROZEN / "offers" / CASE).glob("*.v1.json"))
    assert [p.name for p in sorted((tmp_path / "offers").iterdir())] == [p.name for p in offers]
    for p in offers:
        assert validate_file("offer", (tmp_path / "offers" / p.name).read_text()) == validate_file(
            "offer", p.read_text()
        )
    assert _frozen_hash() == before


def _offer_payload(path: Path) -> dict[str, Any]:
    payload, _ = validate_file("offer", path.read_text())
    assert isinstance(payload, dict)
    return payload


def test_fees_absent_versus_none(template: Path, tmp_path: Path) -> None:
    """LW-02: no fee rows + blank fees_none = fees absent; fees_none=true = fees []."""
    wb = load_workbook(template)
    fees = wb["fees"]
    for row in fees.iter_rows(min_row=kit.DATA_ROW):
        if str(row[0].value) in ("1", "2"):
            for cell in row:
                cell.value = None
    header = [c.value for c in wb["offers"][1]]
    wb["offers"].cell(kit.DATA_ROW, header.index(kit.FEES_NONE) + 1, "true")
    path = tmp_path / "fees.xlsx"
    wb.save(path)
    assert kit.main(["convert", str(path), str(tmp_path / "out")]) == 0
    a, b = sorted((tmp_path / "out" / "offers").iterdir())[:2]
    assert _offer_payload(a)["fees"] == []
    assert "fees" not in _offer_payload(b)


def test_errors_name_tab_row_column(
    template: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    wb = load_workbook(template)
    wb["costs"].cell(kit.DATA_ROW + 1, 2, "rent")  # not a category
    header = [c.value for c in wb["offers"][1]]
    wb["offers"].cell(kit.DATA_ROW + 2, header.index("disbursal_date") + 1, "31-02-2027")
    wb["credit_lines"].cell(kit.DATA_ROW, 1, "9")  # no opening_position row 9
    path = tmp_path / "bad.xlsx"
    wb.save(path)
    out = tmp_path / "out"
    assert kit.main(["convert", str(path), str(out)]) == 1
    err = capsys.readouterr().err
    assert "costs: row 5, column category:" in err
    assert "offers: row 6, column disbursal_date:" in err
    assert "credit_lines: row 4, column row_id:" in err
    assert not out.exists(), "nothing is written when any file fails"


def test_out_under_frozen_is_refused(template: Path) -> None:
    before = _frozen_hash()
    assert kit.main(["convert", str(template), str(FROZEN / "authoring-test")]) == 2
    assert kit.main(["template", "--out", str(FROZEN / "x.xlsx")]) == 2
    assert not (FROZEN / "authoring-test").exists()
    assert _frozen_hash() == before


@pytest.mark.slow
def test_api_results_identical(template: Path, tmp_path: Path) -> None:
    """Frozen files and xlsx-converted files, uploaded to two cases, give the same funding and
    offer views (same KFS for both)."""
    demo = _load("demo_reset")
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        jwt_secret="x" * 40,
        case_db=tmp_path / "case.db",
        tenant_id="demo",
        llm_enabled=False,
        tracing_enabled=False,
        seed_password="fixture-password-123",
    )
    demo.reset_db(settings)
    tree = tmp_path / "tree"
    assert kit.main(["convert", str(template), str(tree / "cases" / CASE)]) == 0
    (tree / "offers").mkdir()
    (tree / "cases" / CASE / "offers").rename(tree / "offers" / CASE)
    (tree / "kfs").symlink_to(FROZEN / "kfs")

    app = create_app(settings.model_copy(update={"rate_limit": "100000/minute"}))
    views = []
    with TestClient(app) as client:
        h = demo._login(client, settings, "demo.preparer")
        for root in (FROZEN, tree):
            demo.FROZEN = root
            cid = demo._case(client, h, CASE, "Demo Electronics Pvt Ltd", True)
            got = [client.get(f"/v1/cases/{cid}{p}", headers=h).json() for p in ("", "/funding")]
            got.append(client.get(f"/v1/cases/{cid}/offers", headers=h).json())
            views.append(json.loads(json.dumps(got).replace(cid, "CASE")))
    head_a, head_b = views[0].pop(0), views[1].pop(0)
    assert (head_a["status"], head_a["route"]) == ("AWAITING_APPROVAL", "director_finance")
    assert (head_b["status"], head_b["route"]) == (head_a["status"], head_a["route"])
    assert views[0] == views[1]
