"""make e2e-report (scripts/e2e_report.py): the pure parts; the full run is done by hand."""

import sys
from pathlib import Path

from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import e2e_report as er

ROOT = Path(__file__).resolve().parents[1]


def test_rupees_indian_grouping() -> None:
    assert er.rupees(14_200_000_00) == "₹1,42,00,000"
    assert er.rupees(0) == "₹0"
    assert er.rupees(15_00_00_00_000) == "₹15,00,00,000"
    assert er.rupees(None) == "—"


def test_every_scenario_folder_has_its_case_fields_and_lenders() -> None:
    folders = sorted(p.name for p in (ROOT / "data" / "test-pack").iterdir() if p.is_dir())
    assert folders == sorted(er.SCENARIOS)  # a new scenario folder needs an expected result
    for f in folders:
        fields = er.new_case_fields(f)
        assert fields["msme_name"].startswith("E2E test") and fields["order_value_paise"] > 0
        assert fields["order_ref"].startswith("PO-CA-2026-")
        assert len(er.lender_names(f)) == 3


def test_writes_only_to_a_private_gateway() -> None:
    gw = er.Gateway(ROOT / "var" / "e2e-report" / "unit")
    assert gw.url.startswith("http://127.0.0.1:")
    assert gw.env["CASE_DB"].endswith("unit/case.db") and gw.env["LLM_ENABLED"] == "false"
    assert gw.env["MFA_ENFORCED"] == "true" and gw.fixture != gw.admin_pw
    assert not any(k.startswith("SEED_PASSWORD") for k in gw.env)


def test_report_files(tmp_path: Path) -> None:
    run = er.Run()
    run.add("Approvals", "VP step-up", "refused", "403", True, case="CA-2026-0001")
    run.add("Evaluator", "read only", "refused", "200", False)
    meta = {"Result": "1 of 2"}
    er.write_xlsx(tmp_path / "r.xlsx", run, meta)
    er.write_html(tmp_path / "r.html", run, meta)
    ws = load_workbook(tmp_path / "r.xlsx")["Results"]
    assert [c.value for c in ws[2]][:6] == [1, "Approvals", "VP step-up", "refused", "403", "Pass"]
    assert ws.cell(3, 6).value == "Fail"
    page = (tmp_path / "r.html").read_text()
    assert "Failures" in page and "1 / 2" in page and "CA-2026-0001" in page
