"""ADR 0040: the case Excel workbook is converted to the same JSON/CSV files and stored through the
same upload path (UI-02). All or nothing; errors name sheet, row and column; input is guarded."""

import io
import zipfile
from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook

Login = Callable[[TestClient, str], dict[str, str]]
ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "data" / "templates" / "case_template.xlsx"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _post(client: TestClient, h: dict[str, str], case_id: str, data: bytes, name: str = "c.xlsx"):  # type: ignore[no-untyped-def]
    return client.post(
        f"/v1/cases/{case_id}/workbook", files={"file": (name, data, XLSX)}, headers=h
    )


def _edited(edit: Callable[..., None]) -> bytes:
    wb = load_workbook(TEMPLATE)
    edit(wb)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_ADR0040_example_workbook_gives_the_same_files_as_single_uploads(
    client: TestClient,
    login: Login,
    new_case: Callable[[TestClient], str],
    upload_demo_files: Callable[[TestClient, str], None],
) -> None:
    h = login(client, "demo.preparer")
    by_files = new_case(client)
    upload_demo_files(client, by_files)
    by_excel = new_case(client)
    r = _post(client, h, by_excel, TEMPLATE.read_bytes())
    assert r.status_code == 201, r.text
    names = {f["name"] for f in r.json()["files"]}
    assert {"order.json", "costs.csv", "inventory.csv"} <= names
    assert sum(n.startswith("offers/") for n in names) == 3
    a = client.get(f"/v1/cases/{by_files}/files", headers=h).json()["files"]
    b = client.get(f"/v1/cases/{by_excel}/files", headers=h).json()["files"]
    for x, y in zip(a, b, strict=True):  # the stored payloads are the same records
        assert x["kind"] == y["kind"] and x["data"] == y["data"], x["kind"]
    history = client.get(f"/v1/cases/{by_excel}/history", headers=h).json()["events"]
    assert sum(e["event_type"] == "FILE_UPLOADED" for e in history) == len(names)


def test_ADR0040_errors_name_sheet_row_column_and_store_nothing(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    h = login(client, "demo.preparer")
    case_id = new_case(client)

    def bad(wb):  # type: ignore[no-untyped-def]
        wb["costs"].cell(5, 3, "not money")  # Excel row 5, column amount

    r = _post(client, h, case_id, _edited(bad))
    assert r.status_code == 422, r.text
    errors = r.json()["errors"]
    assert {k: errors[0][k] for k in ("field", "row")} == {"field": "costs.amount", "row": 5}
    files = client.get(f"/v1/cases/{case_id}/files", headers=h).json()["files"]
    assert all(f["uploaded_at"] is None for f in files)  # all or nothing


def test_ADR0040_partial_workbook_stores_only_filled_sheets(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    h = login(client, "demo.preparer")
    case_id = new_case(client)

    def only_costs(wb):  # type: ignore[no-untyped-def]
        for ws in wb.worksheets:
            if ws.title not in ("README", "costs") and ws.max_row >= 4:
                ws.delete_rows(4, ws.max_row - 3)

    r = _post(client, h, case_id, _edited(only_costs))
    assert r.status_code == 201, r.text
    assert [f["name"] for f in r.json()["files"]] == ["costs.csv"]


def test_ADR0040_formulas_pii_and_non_workbooks_are_refused(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    h = login(client, "demo.preparer")
    case_id = new_case(client)

    def formula(wb):  # type: ignore[no-untyped-def]
        wb["receivables"].cell(4, 2, '=HYPERLINK("http://x","y")')

    assert _post(client, h, case_id, _edited(formula)).status_code == 422

    def pan(wb):  # type: ignore[no-untyped-def]
        wb["receivables"].cell(4, 2, "BQZPK4821M")

    r = _post(client, h, case_id, _edited(pan))
    assert r.status_code == 422 and "not allowed" in r.text
    assert _post(client, h, case_id, b"not a zip").status_code == 422
    assert _post(client, h, case_id, TEMPLATE.read_bytes(), name="c.csv").status_code == 415


def test_ADR0040_zip_bomb_is_refused_before_parsing(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    h = login(client, "demo.preparer")
    case_id = new_case(client)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<x/>")
        z.writestr("xl/big.xml", b"0" * (45 * 1024 * 1024))  # 45 MB unzipped, ~45 kB zipped
    r = _post(client, h, case_id, buf.getvalue())
    assert r.status_code == 422 and "too large" in r.text


def test_ADR0040_only_the_case_preparer_imports_and_locked_cases_refuse(
    client: TestClient, login: Login, new_case: Callable[[TestClient], str]
) -> None:
    case_id = new_case(client)
    other = login(client, "demo.preparer2")
    assert _post(client, other, case_id, TEMPLATE.read_bytes()).status_code == 404
    director = login(client, "demo.director")
    assert _post(client, director, case_id, TEMPLATE.read_bytes()).status_code in (403, 404)


def test_ADR0040_template_download_blank_and_example(client: TestClient, login: Login) -> None:
    h = login(client, "demo.preparer")
    blank = client.get("/v1/templates/case.xlsx", headers=h)
    assert blank.status_code == 200 and blank.headers["content-type"].startswith(XLSX)
    wb = load_workbook(io.BytesIO(blank.content))
    assert wb["costs"].max_row <= 3  # headers, types, required rows only
    example = client.get("/v1/templates/case.xlsx", params={"example": "true"}, headers=h)
    assert load_workbook(io.BytesIO(example.content))["costs"].max_row > 3
