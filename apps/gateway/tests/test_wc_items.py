"""Phase 9b / E6: the 15 frozen cash-flow items (T036-T050) through the API (WC-01..07, API-01).

Each item: create a case, upload the frozen files of its case, run onboarding then working
capital through the agent routes, and compare the stage result and wc.* facts with gold to ₹1.
Model off and on (on: a slot draft must be used, rendered by code to the gold figures).
"""

import json
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from credassure.core.money import format_inr

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "data/frozen/v1/cases"
ITEMS = [
    item
    for item in map(json.loads, (ROOT / "evaluation/testset/v1/items.jsonl").open())
    if item["category"] == "cashflow"
]
KINDS = ("order", "opening_position", "costs", "receipts", "receivables", "payables", "inventory")
NEW_CASE = {
    "msme_name": "Demo Electronics Pvt Ltd",
    "order_ref": "PO-WC",
    "order_value_paise": 3_20_00_000_00,
    "indicative_amount_paise": 2_00_00_000_00,  # every gold bridge starts at ₹2 crore
    "due_date": "2027-05-15",
}
Login = Callable[[TestClient, str], dict[str, str]]


def upload(client: TestClient, h: dict[str, str], case_id: str, kind: str, body: bytes) -> None:
    name = f"{kind}.json" if kind in ("order", "opening_position") else f"{kind}.csv"
    r = client.post(
        f"/v1/cases/{case_id}/files",
        params={"kind": kind},
        files={"file": (name, body, "application/json" if name.endswith("json") else "text/csv")},
        headers=h,
    )
    assert r.status_code == 201, (kind, r.text)


def start(
    client: TestClient, login: Login, frozen: str, edit: Callable[[str, bytes], bytes] | None = None
) -> tuple[str, dict[str, str]]:
    h = login(client, "demo.preparer")
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    for kind in KINDS:
        name = f"{kind}.json" if kind in ("order", "opening_position") else f"{kind}.csv"
        body = (CASES / frozen / name).read_bytes()
        upload(client, h, case_id, kind, edit(kind, body) if edit else body)
    r = client.post(f"/v1/agents/onboarding/cases/{case_id}/run", headers=h)
    assert r.status_code == 202, r.text
    return case_id, h


def run_wc(client: TestClient, case_id: str, h: dict[str, str]) -> dict[str, Any]:
    r = client.post(f"/v1/agents/working-capital/cases/{case_id}/run", headers=h)
    assert r.status_code == 202, r.text
    r = client.get(f"/v1/agents/working-capital/cases/{case_id}/result", headers=h)
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


def facts(client: TestClient, case_id: str, h: dict[str, str]) -> dict[str, str]:
    r = client.get(f"/v1/cases/{case_id}/funding", headers=h)
    assert r.status_code == 200, r.text
    return {f["key"]: f["value"] for f in r.json()["facts"]}


def near(got: str, want: float) -> bool:
    return abs(Decimal(got) - Decimal(str(want))) <= 1  # ₹1 (BRD §13)


@pytest.mark.parametrize("llm_enabled", [False, True])
def test_WC03_E6_fifteen_frozen_cashflow_items_through_the_api(
    make_client: Callable[..., Any], login: Login, llm_enabled: bool
) -> None:
    # 15 cases x ~11 calls exceeds the per-user limit (NFR-04), which other tests cover
    client = make_client(llm_enabled=llm_enabled, rate_limit="10000/minute")
    passed = []
    for item in ITEMS:
        gold = item["gold"]
        if client.llm is not None and gold["gate"] == "GO":
            drafted = (
                f"Cash is lowest in week {gold['peak_week']}, so the recommended facility is "
                f"{format_inr(Decimal(gold['recommended_amount']))} against the request of "
                f"{format_inr(Decimal('20000000'))}."
            )
            client.llm.replies = {  # the model writes slots; code renders the figures above
                "wc_explain": [
                    "Cash is lowest in week {wc.peak_week}, so the recommended facility is "
                    "{wc.recommended_amount} against the request of {wc.request}."
                ]
            }
        case_id, h = start(client, login, item["input"]["case_id"])
        result = run_wc(client, case_id, h)
        assert result["decision"] == gold["gate"], item["id"]
        f = facts(client, case_id, h)
        if gold["gate"] == "GO":
            assert near(f["wc.recommended_amount"], gold["recommended_amount"]), item["id"]
            assert near(f["wc.peak_shortfall"], gold["peak_shortfall"]), item["id"]
            assert f["wc.peak_week"] == str(gold["peak_week"]), item["id"]
            for line in gold["bridge"]:
                assert near(f[f"wc.bridge.{line['line']}"], line["amount"]), (item["id"], line)
            bridge = sum(Decimal(v) for k, v in f.items() if k.startswith("wc.bridge."))
            assert bridge == Decimal(f["wc.recommended_amount"]), item["id"]  # WC-06 exact
            r = client.get(f"/v1/cases/{case_id}/funding", headers=h).json()
            assert r["recommended_amount"]["paise"] == int(gold["recommended_amount"]) * 100
            if client.llm is not None:
                assert result["narrative"] == drafted, item["id"]  # the model's wording was used
        else:
            got = [(b["code"], b["field"].split(".")[-1]) for b in result["blockers"]]
            want = [(b["code"], b["field"].split(".")[-1]) for b in gold["blockers"]]
            assert got == want, item["id"]
            assert result["question"] and result["question"].count("?") == 1, item["id"]
            assert "wc.recommended_amount" not in f, item["id"]
        passed.append(item["id"])
    assert len(passed) == 15


def test_SUP06_E6_missing_field_resumes_only_the_blocked_stage(client: Any, login: Login) -> None:
    """T048: NEEDS_INPUT names min_cash_buffer; the corrected upload re-runs WC alone."""
    from credassure.ledger import reads, session

    case_id, h = start(client, login, "CA-2026-0013")
    first = run_wc(client, case_id, h)
    assert first["decision"] == "NEEDS_INPUT" and "min cash buffer" in first["question"]
    view = client.get(f"/v1/cases/{case_id}", headers=h).json()
    assert view["status"] == "PAUSED" and view["question"] == first["question"]
    opening = json.loads((CASES / "CA-2026-0013/opening_position.json").read_text())
    opening["min_cash_buffer"] = 800000
    upload(client, h, case_id, "opening_position", json.dumps(opening).encode())
    funding = client.get(f"/v1/cases/{case_id}/funding", headers=h).json()
    assert funding["recommended_amount"] is None  # nothing shown before a GO
    bad = dict(opening, min_cash_buffer="1E+7")
    r = client.post(
        f"/v1/cases/{case_id}/files",
        params={"kind": "opening_position"},
        files={"file": ("opening_position.json", json.dumps(bad).encode(), "application/json")},
        headers=h,
    )
    assert r.status_code == 422 and "plain digits" in r.text  # field-level, not a stage crash
    again = run_wc(client, case_id, h)
    assert again["decision"] == "GO"
    with session.transaction(session.case_engine(client.db)) as s:
        runs = [r.stage for r in reads.stage_runs(s, "default", case_id)]
    assert runs.count("onboarding") == 1 and runs.count("working_capital") == 2


def test_SUP05_E9S2_wrong_wc_fact_is_overridden_and_audited(client: Any, login: Login) -> None:
    """The agent says GO but writes a wrong amount; the re-check recomputes and overrides it."""
    from credassure.agents.working_capital import agent as wc
    from credassure.core.enums import Stage
    from credassure.ledger import reads, session

    sup = client.app.state.services.supervisor

    def lying(ctx: Any) -> Any:
        result = wc.run(ctx)
        ctx.ledger.put_fact(
            ctx.case_id,
            "wc.recommended_amount",
            Decimal("20000000"),  # the indicative request, never the default (BR-01)
            unit="INR",
            source_type="case_file",
            source_ref="tamper",
            produced_by="test",
        )
        return result

    sup.agents = {**sup.agents, Stage.WORKING_CAPITAL: lying}
    case_id, h = start(client, login, "CA-2026-0001")
    result = run_wc(client, case_id, h)
    assert result["decision"] == "NO_GO"
    assert "SUP_RECHECK_MISMATCH" in {b["code"] for b in result["blockers"]}
    with session.transaction(session.case_engine(client.db)) as s:
        events = [e.event_type for e in reads.audit_events(s, "default", case_id)]
        runs = {r.stage for r in reads.stage_runs(s, "default", case_id)}
    assert "GATE_OVERRIDE" in events and "lendwise" not in runs


def _indian(kind: str, body: bytes) -> bytes:
    """Rewrite every costs amount in Indian grouping (DATA_SPEC §2): same figures, same need."""
    if kind != "costs":
        return body
    lines = body.decode().splitlines()
    out = [lines[0]]
    for line in lines[1:]:
        week, category, amount = line.split(",")
        out.append(f'{week},{category},"{format_inr(Decimal(amount))}"')
    return ("\n".join(out) + "\n").encode()


def test_WC04_cash_table_endpoint_and_lineage(client: Any, login: Login) -> None:
    from credassure.ledger import reads, session

    case_id, h = start(client, login, "CA-2026-0001", edit=_indian)  # costs as "₹13,38,300"
    url = f"/v1/agents/working-capital/cases/{case_id}/cash-table"
    assert client.get(url, headers=h).status_code == 404  # before the stage runs
    run_wc(client, case_id, h)
    rows = client.get(url, headers=h).json()["rows"]
    assert [r["week"] for r in rows] == list(range(1, 27))
    lowest = min(rows, key=lambda r: r["cumulative"]["paise"])
    assert lowest["week"] == 9 and lowest["cumulative"]["paise"] == -16_200_000_00
    other = login(client, "prep.e001")  # another preparer: the case policy applies
    assert client.get(url, headers=other).status_code in (403, 404)
    with session.transaction(session.case_engine(client.db)) as s:
        fact = reads.get_latest(s, "default", case_id, "wc.recommended_amount")
        files = reads.case_files(s, "default", case_id)
    assert fact is not None and fact.source_type == "case_file"
    assert fact.produced_by.startswith("engines.cashflow@") and len(fact.input_hash) == 64
    costs = next(f for f in files if f.kind == "costs")
    assert f"costs@{costs.sha256[:12]}" in fact.source_ref  # lineage names the stored file


def test_SUP06_E6_conflicting_case_resumes_only_the_blocked_stage(
    client: Any, login: Login
) -> None:
    """T049: one question for conflicting totals and duplicate IDs; corrected files re-run WC."""
    from credassure.ledger import reads, session

    case_id, h = start(client, login, "CA-2026-0014")
    first = run_wc(client, case_id, h)
    assert first["decision"] == "NEEDS_INPUT" and first["question"].count("?") == 1
    for kind in ("order", "receipts", "receivables"):  # consistent files replace the bad ones
        name = f"{kind}.json" if kind == "order" else f"{kind}.csv"
        upload(client, h, case_id, kind, (CASES / "CA-2026-0001" / name).read_bytes())
    assert run_wc(client, case_id, h)["decision"] == "GO"
    with session.transaction(session.case_engine(client.db)) as s:
        runs = [r.stage for r in reads.stage_runs(s, "default", case_id)]
    assert runs.count("onboarding") == 1 and runs.count("working_capital") == 2


def test_WC05_unsourced_offset_is_refused_at_upload(client: Any, login: Login) -> None:
    h = login(client, "demo.preparer")
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    opening = json.loads((CASES / "CA-2026-0001/opening_position.json").read_text())
    opening["confirmed_mitigations"] = [
        {"type": "advance", "amount": 5000000, "week": 2, "evidence_ref": ""}
    ]
    r = client.post(
        f"/v1/cases/{case_id}/files",
        params={"kind": "opening_position"},
        files={"file": ("opening_position.json", json.dumps(opening).encode(), "application/json")},
        headers=h,
    )
    assert r.status_code == 422 and "evidence_ref" in r.text
