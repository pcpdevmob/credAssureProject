"""Plan v3.4 P8.3 (scope #67, ADR 0029 R1): a case file with a protected-attribute field is refused
and the refusal is an audited guardrail block. Values (names) are never inspected."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from credassure.ledger import reads, session

DEMO = Path(__file__).resolve().parents[3] / "data" / "frozen" / "v1" / "cases" / "CA-2026-0001"
NEW_CASE = {
    "msme_name": "Demo Electronics Pvt Ltd",
    "order_ref": "PO-P8",
    "order_value_paise": 3_20_00_000_00,
    "indicative_amount_paise": 2_00_00_000_00,
    "due_date": "2027-05-15",
}


def _order(**extra: Any) -> bytes:
    order = json.loads((DEMO / "order.json").read_text())
    order.update(extra)
    return json.dumps(order).encode()


def _receivables(extra_col: str) -> bytes:
    lines = (DEMO / "receivables.csv").read_text().splitlines()
    out = [f"{lines[0]},{extra_col}"] + [f"{line},x" for line in lines[1:]]
    return ("\n".join(out) + "\n").encode()


@pytest.mark.parametrize(
    ("kind", "name", "body", "field"),
    [
        ("order", "order.json", _order(promoter_gender="F"), "promoter_gender"),
        ("order", "order.json", _order(owner={"religion": "x"}), "religion"),
        ("order", "order.json", _order(dateOfBirth="1980-01-01"), "dateOfBirth"),
        ("order", "order.json", _order(community="x"), "community"),
        ("receivables", "receivables.csv", _receivables("customer_caste"), "customer_caste"),
        ("receivables", "receivables.csv", _receivables("Age"), "Age"),
    ],
)
def test_scope67_protected_attribute_field_is_refused_and_audited(
    client: Any,
    login: Callable[..., dict[str, str]],
    kind: str,
    name: str,
    body: bytes,
    field: str,
) -> None:
    h = login(client, "prep.e001")
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    mime = "application/json" if name.endswith(".json") else "text/csv"
    r = client.post(
        f"/v1/cases/{case_id}/files",
        params={"kind": kind},
        files={"file": (name, body, mime)},
        headers=h,
    )
    assert r.status_code == 422, r.text
    assert [e["field"] for e in r.json()["errors"]] == [field]
    with session.transaction(session.case_engine(client.db)) as s:
        events = [
            e.payload
            for e in reads.audit_events(s, "default", case_id)
            if e.event_type == "GUARDRAIL_EVENT"
        ]
    assert [(e["rule_id"], e["action"], e["fields"]) for e in events] == [
        ("R1.upload_protected_attribute", "block", [field])
    ]


def test_scope67_ordinary_fields_and_names_are_accepted(
    client: Any, login: Callable[..., dict[str, str]]
) -> None:
    """The frozen demo files pass; a name that sounds like a community is a value, not a field."""
    h = login(client, "prep.e001")
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    r = client.post(
        f"/v1/cases/{case_id}/files",
        params={"kind": "order"},
        files={"file": ("order.json", _order(customer_name="Fatima Traders"), "application/json")},
        headers=h,
    )
    assert r.status_code == 201, r.text
