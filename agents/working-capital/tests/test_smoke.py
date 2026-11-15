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
    assert agent.version() == "0.2.0"


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
    assert agent.grounded(result.narrative, agent.facts_for(table, rec), 26)


def _engine(inputs: agent.CaseInputs) -> tuple[Any, Any]:
    assert inputs.files is not None
    table = cashflow.cash_table(inputs.files)
    return table, cashflow.recommend(inputs.files, table, indicative=inputs.indicative)


def test_WC07_model_wording_used_only_when_every_number_is_a_fact() -> None:
    inputs = agent.load_inputs(stored(), INDICATIVE)
    good = (
        "Cash is lowest in week 9 at a shortfall of ₹1,62,00,000. After the buffer of ₹10,00,000"
        " and undrawn limits of ₹30,00,000, the facility is ₹1,42,00,000, not ₹2,00,00,000."
    )
    result, _, _ = run(inputs, FakeLLM(replies={"wc_explain": [good]}))
    assert result.narrative == good and result.prompt_versions == {"wc_explain": "1.0.0"}
    for bad in (
        good.replace("₹1,42,00,000", "₹1,45,00,000"),  # invented amount
        good + " Interest is 11% a year.",  # a rate
        good.replace("week 9", "week 11"),  # wrong week
        good + " Lenders will approve it.",  # approval prediction
    ):
        result, _, _ = run(inputs, FakeLLM(replies={"wc_explain": [bad]}))
        assert result.narrative != bad and "₹1,42,00,000" in str(result.narrative)


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
    assert ledger.facts == {"wc.gate": "NEEDS_INPUT"}


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


@pytest.mark.parametrize(
    "extra",
    [
        " Plan for Q1 FY27.",
        " See https://x.example/a.",
        " You need two crore rupees.",
        " Rate is twelve percent.",
        " Bank X will sanction quickly.",
    ],
)
def test_WC07_guard_refuses_unsourced_figures_in_words_ids_links_and_lender_talk(
    extra: str,
) -> None:
    inputs = agent.load_inputs(stored(), INDICATIVE)
    good = "The facility is ₹1,42,00,000 against ₹2,00,00,000."
    result, _, _ = run(inputs, FakeLLM(replies={"wc_explain": [good + extra]}))
    assert result.narrative != good + extra
    result, _, _ = run(inputs, FakeLLM(replies={"wc_explain": [good]}))
    assert result.narrative == good


def test_WC07_zero_need_template_names_the_dip_and_what_covers_it() -> None:
    inputs = agent.load_inputs(stored("CA-2026-0015"), INDICATIVE)
    result, ledger, _ = run(inputs)
    assert Decimal(ledger.facts["wc.recommended_amount"]) == 0
    assert "peak shortfall of ₹40,00,000 in week 7" in str(result.narrative)
    assert "no new facility" in str(result.narrative)


@pytest.mark.parametrize("case", sorted(p.name for p in CASES.iterdir()))
def test_WC07_template_always_passes_its_own_guard(case: str) -> None:
    inputs = agent.load_inputs(stored(case), INDICATIVE)
    if inputs.blockers:
        pytest.skip("NEEDS_INPUT case: no figures")
    table, rec = _engine(inputs)
    assert agent.grounded(agent.template(rec, table), agent.facts_for(table, rec), 26)
