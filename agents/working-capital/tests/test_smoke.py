"""Working Capital agent units (WC-01..07, SUP-05/06) with FakeLLM and an in-memory ledger.

Inputs are the frozen demo case files (CA-2026-0001; gold need ₹1,42,00,000, peak ₹1,62,00,000
in week 9). The full 15-item set runs through the API in apps/gateway/tests/test_wc_items.py.
"""

import csv
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from credassure.agents.working_capital import agent
from credassure.core.enums import Decision, Stage
from credassure.core.ports import StageContext
from credassure.engines import cashflow
from credassure.llm.fake import FakeLLM

CASES = Path(__file__).resolve().parents[3] / "data/frozen/v1/cases"
INDICATIVE = Decimal("20000000")


def stored(case: str = "CA-2026-0001") -> dict[str, tuple[str, Any]]:
    out: dict[str, tuple[str, Any]] = {}
    for kind, name in agent.FILES.items():
        path = CASES / case / name
        if name.endswith(".json"):
            out[kind] = (f"sha-{kind}", json.loads(path.read_text()))
        else:
            out[kind] = (f"sha-{kind}", list(csv.DictReader(path.open())))
    return out


class Ledger:
    def __init__(self) -> None:
        self.facts: dict[str, str] = {}
        self.meta: dict[str, dict[str, Any]] = {}

    def get(self, case_id: str, key: str) -> str | None:
        return self.facts.get(key)

    def put_fact(self, case_id: str, key: str, value: Decimal | int | str, **meta: Any) -> int:
        self.facts[key], self.meta[key] = str(value), meta
        return 1


class Tools:
    def __init__(self, inputs: agent.CaseInputs) -> None:
        self.inputs = inputs
        self.called: list[str] = []

    def call(self, name: str, case_id: str, args: Any = None) -> Any:
        self.called.append(name)
        a = args or {}
        if name == "validate_case_files":
            return self.inputs
        if name == "compute_cash_table":
            return cashflow.cash_table(a["files"], a["weeks"])
        if name == "compute_recommendation":
            return cashflow.recommend(a["files"], a["table"], indicative=a["indicative"])
        raise AssertionError(name)


class Clock:
    def today(self) -> date:
        return date(2026, 11, 15)


def run(inputs: agent.CaseInputs, llm: Any = None) -> tuple[Any, Ledger, Tools]:
    ledger, tools = Ledger(), Tools(inputs)
    ctx = StageContext(
        case_id="CA-T",
        tenant_id="default",
        stage=Stage.WORKING_CAPITAL,
        trace_id="t1",
        ledger=ledger,
        tools=tools,
        llm=llm,
        clock=Clock(),
    )
    return agent.run(ctx), ledger, tools


def test_smoke_version() -> None:
    assert agent.version() == "0.2.1"


def test_WC03_WC06_demo_case_go_with_facts_bridge_and_lineage() -> None:
    inputs = agent.load_inputs(stored(), INDICATIVE)
    result, ledger, tools = run(inputs)
    assert result.decision is Decision.GO and not result.question
    f = ledger.facts
    assert Decimal(f["wc.recommended_amount"]) == 14_200_000  # BR-01: not the ₹2 cr request
    assert Decimal(f["wc.peak_shortfall"]) == 16_200_000 and f["wc.peak_week"] == "9"
    bridge = [Decimal(v) for k, v in f.items() if k.startswith("wc.bridge.")]
    assert sum(bridge) == Decimal(f["wc.recommended_amount"])  # WC-06: sums exactly
    assert len(json.loads(f["wc.cash_table"])) == 26
    meta = ledger.meta["wc.recommended_amount"]  # lineage (#33)
    assert meta["input_hash"] == inputs.input_hash and len(meta["input_hash"]) == 64
    assert meta["source_ref"].startswith("case_files:") and "costs@sha-costs" in meta["source_ref"]
    assert meta["produced_by"].startswith("engines.cashflow@")
    assert tools.called == ["validate_case_files", "compute_cash_table", "compute_recommendation"]
    table, rec = _engine(inputs)
    assert result.narrative == agent.template(rec, table)  # LLM off: the template


def _engine(inputs: agent.CaseInputs) -> tuple[Any, Any]:
    assert inputs.files is not None
    table = cashflow.cash_table(inputs.files)
    return table, cashflow.recommend(inputs.files, table, indicative=inputs.indicative)


DRAFT = (
    "Cash is lowest in week {wc.peak_week}, a shortfall of {wc.peak_shortfall}. With the buffer of"
    " {wc.min_buffer} and undrawn limits of {wc.undrawn_limits}, the facility of"
    " {wc.recommended_amount} is {cmp.recommended_vs_request} the request of {wc.request}."
)
RENDERED = (
    "Cash is lowest in week 9, a shortfall of ₹1,62,00,000. With the buffer of ₹10,00,000 and"
    " undrawn limits of ₹30,00,000, the facility of ₹1,42,00,000 is lower than the request of"
    " ₹2,00,00,000."
)


def test_WC07_code_renders_every_slot_and_direction_word() -> None:
    inputs = agent.load_inputs(stored(), INDICATIVE)
    result, _, _ = run(inputs, FakeLLM(replies={"wc_explain": [DRAFT]}))
    assert result.narrative == RENDERED and result.prompt_versions == {"wc_explain": "2.0.0"}


@pytest.mark.parametrize(
    "bad",
    [
        DRAFT.replace("{wc.recommended_amount}", "₹1,45,00,000"),  # a figure of its own
        DRAFT.replace("{wc.recommended_amount}", "₹1,42,00,000"),  # even a right one
        DRAFT.replace("{wc.peak_week}", "11"),
        DRAFT.replace("{wc.undrawn_limits}", "{wc.mitigations}"),  # zero offset has no slot
        DRAFT.replace("{cmp.recommended_vs_request}", "higher than"),  # direction of its own
        DRAFT.replace("{wc.request}", "{wc.indicative}"),  # unknown slot
        "Cash is short in {wc.peak_week}.",  # never names the facility
    ],
)
def test_WC07_any_figure_or_direction_outside_a_slot_falls_back(bad: str) -> None:
    inputs = agent.load_inputs(stored(), INDICATIVE)
    result, _, _ = run(inputs, FakeLLM(replies={"wc_explain": [bad]}))
    table, rec = _engine(inputs)
    assert result.narrative == agent.template(rec, table)


def test_WC07_model_sees_slot_names_never_values() -> None:
    llm = FakeLLM(replies={"wc_explain": [DRAFT]})
    run(agent.load_inputs(stored(), INDICATIVE), llm)
    ((_, prompt),) = llm.calls
    assert "wc.recommended_amount" in prompt
    assert "1,42" not in prompt and "1,62" not in prompt
    assert "wc.mitigations" not in prompt.split("<slots>")[1].split("</slots>")[0]


def test_WC01_missing_field_needs_input_with_one_question_naming_it() -> None:
    files = stored()
    opening = dict(files["opening_position"][1])
    del opening["min_cash_buffer"]
    files["opening_position"] = ("sha-x", opening)
    result, ledger, tools = run(agent.load_inputs(files, INDICATIVE))
    assert result.decision is Decision.NEEDS_INPUT
    assert [b.field for b in result.blockers] == ["opening_position.min_cash_buffer"]
    assert "min cash buffer" in str(result.question) and "opening_position.json" in str(
        result.question
    )
    assert tools.called == ["validate_case_files"]  # no cash table on bad inputs
    assert set(ledger.facts) == {"wc.gate", "wc.narrative"}  # 9d: the shown text is recorded
    assert ledger.facts["wc.gate"] == "NEEDS_INPUT"


def test_WC01_missing_file_is_named_before_validation() -> None:
    files = stored()
    del files["payables"]
    result, _, _ = run(agent.load_inputs(files, INDICATIVE))
    assert result.decision is Decision.NEEDS_INPUT
    assert [b.field for b in result.blockers] == ["payables"]
    assert result.question == "Can you upload payables.csv for this case?"


def test_WC02_conflicting_case_asks_one_question_about_the_first_priority_blocker() -> None:
    result, _, _ = run(agent.load_inputs(stored("CA-2026-0014"), INDICATIVE))
    assert result.decision is Decision.NEEDS_INPUT
    codes = [b.code.value for b in result.blockers]
    assert codes == ["WC_CONFLICT_TOTALS", "WC_DUPLICATE_ID"]
    assert result.question and result.question.count("?") == 1
    assert "receipts.csv" in result.question  # CONFLICT_TOTALS outranks DUPLICATE_ID


def test_WC05_unsourced_mitigation_never_offsets_the_need() -> None:
    files = stored()
    opening = dict(files["opening_position"][1])
    opening["confirmed_mitigations"] = [{"type": "advance", "amount": "5000000", "week": 2}]
    files["opening_position"] = ("sha-x", opening)
    _, ledger, _ = run(agent.load_inputs(files, INDICATIVE))
    assert Decimal(ledger.facts["wc.mitigations"]) == 0
    assert Decimal(ledger.facts["wc.recommended_amount"]) == 14_200_000


@pytest.mark.parametrize("key", ["wc.recommended_amount", "wc.bridge.min_cash_buffer", "wc.gate"])
def test_SUP05_recheck_flags_any_tampered_fact(key: str) -> None:
    inputs = agent.load_inputs(stored(), INDICATIVE)
    result, ledger, _ = run(inputs)
    check = agent.make_recheck(lambda case_id: inputs)
    assert check(result, ledger) == []  # type: ignore[arg-type]
    ledger.facts[key] = "1"
    found = check(result, ledger)  # type: ignore[arg-type]
    assert [b.code.value for b in found] == ["SUP_RECHECK_MISMATCH"] and key in found[0].message


def test_WC07_zero_need_template_names_the_dip_and_what_covers_it() -> None:
    inputs = agent.load_inputs(stored("CA-2026-0015"), INDICATIVE)
    result, ledger, _ = run(inputs)
    assert Decimal(ledger.facts["wc.recommended_amount"]) == 0
    assert "peak shortfall of ₹40,00,000 in week 7" in str(result.narrative)
    assert "no new facility" in str(result.narrative)


def test_scope1_A1_model_calculates_the_recommendation_and_without_a_model_asks() -> None:
    """Ablation A1 (BRD §12): the model's amount replaces the engine's; never in the product."""
    from dataclasses import replace

    inputs = agent.load_inputs(stored(), INDICATIVE)
    ledger, tools = Ledger(), Tools(inputs)
    base = StageContext(
        case_id="CA-T",
        tenant_id="default",
        stage=Stage.WORKING_CAPITAL,
        trace_id="t1",
        ledger=ledger,
        tools=tools,
        llm=FakeLLM(replies={"a1_wc_calc": ["₹1,50,00,000"]}),
        clock=Clock(),
        ablation="A1",
    )
    result = agent.run(base)
    assert ledger.facts["wc.recommended_amount"] == "15000000"  # the engine says 14200000
    assert result.prompt_versions["a1_wc_calc"] == "1.0.0"
    off = agent.run(replace(base, llm=None, ledger=Ledger()))
    assert off.decision is Decision.NEEDS_INPUT and "A1" in (off.question or "")
