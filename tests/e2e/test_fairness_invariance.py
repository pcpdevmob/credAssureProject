"""Fairness invariance (plan v3.4 P8.3, scope #67, BR-12, ADR 0029).

Gates, the recommended amount, the approval route and the offer ranking are decided by code from
amounts and dates only. Changing who the MSME is, who its customers and suppliers are, or which
state it is in must change none of them. The variants keep every number byte-identical.
"""

import csv
import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

DEMO = Path(__file__).resolve().parents[2] / "data" / "frozen" / "v1" / "cases" / "CA-2026-0001"
KINDS = ("order", "opening_position", "costs", "receipts", "receivables", "payables", "inventory")

# (msme_name, customer_name, home_state, counterparty prefix) — names chosen to vary region,
# community-associated surnames and gendered names; all synthetic.
VARIANTS = [
    ("Demo Electronics Pvt Ltd", None, None, None),  # baseline: the frozen files unchanged
    ("Lakshmi Devi Components LLP", "Fatima Traders", "IN-TN", "Kaur Enterprises"),
    ("Mohammed Iqbal Circuits Pvt Ltd", "Sharma & Sons", "IN-UP", "Fernandes Supplies"),
    ("Brahmaputra Circuits LLP", "Banerjee Distributors", "IN-AS", "Patel Metals"),
]


def _rename_csv(text: str, column: str, prefix: str) -> str:
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or column not in rows[0]:
        return text
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    for i, row in enumerate(rows, 1):
        row[column] = f"{prefix} {i}"
        writer.writerow(row)
    return out.getvalue()


def _files(customer: str | None, state: str | None, prefix: str | None) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for kind in KINDS:
        name = f"{kind}.json" if kind in ("order", "opening_position") else f"{kind}.csv"
        raw = (DEMO / name).read_text()
        if kind == "order" and customer and state:
            order = json.loads(raw)
            order["customer_name"], order["home_state"] = customer, state
            raw = json.dumps(order, indent=2, sort_keys=True)
        if prefix and kind == "receivables":
            raw = _rename_csv(raw, "customer", prefix)
        if prefix and kind == "payables":
            raw = _rename_csv(raw, "supplier", prefix)
        files[name] = raw.encode()
    return files


def _outcome(
    client: TestClient,
    prep: dict[str, str],
    upload_offers: Callable[[TestClient, str, dict[str, str]], None],
    variant: tuple[str, str | None, str | None, str | None],
) -> dict[str, Any]:
    msme, customer, state, prefix = variant
    r = client.post(
        "/v1/cases",
        json={
            "msme_name": msme,
            "order_ref": "PO-CA-2026-0001",
            "order_value_paise": 3_20_00_000_00,
            "indicative_amount_paise": 2_00_00_000_00,
            "due_date": "2027-05-15",
        },
        headers=prep,
    )
    assert r.status_code == 201, r.text
    case_id = r.json()["case_id"]
    for name, body in _files(customer, state, prefix).items():
        kind = name.rsplit(".", 1)[0]
        mime = "application/json" if name.endswith(".json") else "text/csv"
        up = client.post(
            f"/v1/cases/{case_id}/files",
            params={"kind": kind},
            files={"file": (name, body, mime)},
            headers=prep,
        )
        assert up.status_code == 201, (kind, up.text)
    upload_offers(client, case_id, prep)
    run = client.post(f"/v1/cases/{case_id}/run", headers=prep)
    assert run.status_code == 202, run.text
    job = client.get(run.json()["status_url"], headers=prep).json()

    case = client.get(f"/v1/cases/{case_id}", headers=prep).json()
    funding = client.get(f"/v1/cases/{case_id}/funding", headers=prep).json()
    offers = client.get(f"/v1/cases/{case_id}/offers", headers=prep).json()
    return {
        "job": (job["status"], job["outcome"]),
        "stages": [(s["stage"], s["decision"]) for s in case["stages"]],
        "route": case["route"],
        "recommended": funding["recommended_amount"]["paise"],
        "gate": offers["gate"],
        "ranking": offers["ranking"],
    }


@pytest.mark.parametrize("llm_enabled", [True, False])
def test_scope67_BR12_names_and_state_do_not_change_decisions(
    make_client: Callable[[bool], tuple[TestClient, Any]],
    login: Callable[[TestClient, str], dict[str, str]],
    upload_offers: Callable[[TestClient, str, dict[str, str]], None],
    llm_enabled: bool,
) -> None:
    client, _ = make_client(llm_enabled)
    prep = login(client, "demo.preparer")
    outcomes = [_outcome(client, prep, upload_offers, v) for v in VARIANTS]
    base = outcomes[0]
    assert base["route"] == "director_finance" and base["recommended"] == 1_42_00_000_00
    assert base["ranking"] == ["OF-01-B", "OF-01-A"]
    for variant, got in zip(VARIANTS[1:], outcomes[1:], strict=True):
        assert got == base, variant[0]
