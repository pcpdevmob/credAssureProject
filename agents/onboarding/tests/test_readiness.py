import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from readiness import generate_hr_data as gen
from readiness.checker import evaluate_readiness
from readiness.explain import explain, guard_explanation, template_explanation
from readiness.gate import run_readiness_gate
from readiness.graph import build_demo_graph
from readiness.schemas import CheckOutcome, Decision
from readiness.tools import get_employee_record, get_training_status

AS_OF = gen.AS_OF


@pytest.fixture(autouse=True)
def env(hr_env):
    return hr_env


def run(emp_id, llm=None):
    return run_readiness_gate("CASE-T", emp_id, as_of=AS_OF, llm=llm)


# ---------- data ----------
def test_twenty_profiles_and_seeded():
    a, b = gen.build_profiles(), gen.build_profiles()
    assert len(a[0]) == 20 and a == b
    assert len(a[2]) > 0        # policy acknowledgements present


# ---------- decisions ----------
@pytest.mark.parametrize("emp_id,expected,label",
                         [(s[0], s[5], s[6]) for s in gen.SCENARIOS])
def test_every_scenario_decision(emp_id, expected, label):
    assert run(emp_id).decision.value == expected, label


def test_unknown_employee_needs_input():
    r = run("EMP-999")
    assert r.decision == Decision.NEEDS_INPUT and r.blockers == ["EMPLOYEE_FOUND"]


def test_completed_without_evidence_never_passes():
    for emp_id in ("EMP-015", "EMP-018"):
        chk = next(c for c in run(emp_id).checks if c.check_id == "TRAINING:FINDATA")
        assert chk.outcome != CheckOutcome.PASS and chk.reason_code == "NO_EVIDENCE"


def test_expiry_boundaries():
    assert run("EMP-005").decision == Decision.GO          # valid through today
    assert run("EMP-005").warnings                          # but warned
    r = run("EMP-010")
    assert r.decision == Decision.NO_GO and r.blockers == ["TRAINING:COC"]


def test_all_blockers_listed():
    assert set(run("EMP-014").blockers) == {"TRAINING:FINDATA", "TRAINING:INFOSEC", "TRAINING:WCPROC"}


def test_optional_course_ignored():
    """EMP-006 also holds an optional course; it never becomes a rule. Only the credit-policy ack blocks."""
    r = run("EMP-006")
    assert r.blockers == ["ACK:POL_CREDIT"]
    assert not any("EXCEL" in c.check_id for c in r.checks)


# ---------- policy acknowledgements (ONB-02) ----------
def test_every_rule_type_is_checked_with_three_valued_outcome():
    r = run("EMP-001")
    ids = {c.check_id for c in r.checks}
    assert {"ROLE_AUTHORISED", "TRAINING:FINDATA", "ACK:POL_CREDIT", "ACK:POL_DATA"} <= ids
    assert {c.outcome.value for c in run("EMP-018").checks} <= {"pass", "fail", "unknown"}


def test_missing_acknowledgement_is_no_go():
    r = run("EMP-006")
    chk = next(c for c in r.checks if c.check_id == "ACK:POL_CREDIT")
    assert r.decision == Decision.NO_GO and chk.outcome == CheckOutcome.FAIL
    assert "acknowledge" in r.next_action.lower()


def test_expired_acknowledgement_is_no_go():
    r = run("EMP-003")
    assert r.decision == Decision.NO_GO and r.blockers == ["ACK:POL_DATA"]


def test_old_hr_store_without_ack_table_gives_error(tmp_path, monkeypatch):
    emps, recs, _, _ = gen.build_profiles()
    gen.write_db(tmp_path / "old.db", emps, recs)        # no acknowledgements table
    con = sqlite3.connect(tmp_path / "old.db"); con.execute("DROP TABLE IF EXISTS policy_acknowledgements"); con.commit(); con.close()
    monkeypatch.setenv("CREDASSURE_HR_DB", str(tmp_path / "old.db"))
    assert run("EMP-001").decision == Decision.ERROR


def test_result_carries_trace_and_output_reference():
    r = run("EMP-001")
    assert r.agent == "employee_onboarding" and len(r.trace_id) == 32
    assert r.output_ref.startswith("audit_events:")


def test_deterministic():
    a, b = run("EMP-014"), run("EMP-014")
    per_run = {"created_at", "trace_id", "output_ref"}     # differ by design: one trace per run
    assert a.model_dump(exclude=per_run) == b.model_dump(exclude=per_run)


def test_hr_store_down_gives_error(monkeypatch, tmp_path):
    monkeypatch.setenv("CREDASSURE_HR_DB", str(tmp_path / "missing.db"))
    assert run("EMP-001").decision == Decision.ERROR


def test_facts_for_ledger_have_sources():
    r = run("EMP-007")
    assert any(f.key == "readiness.decision" and f.value == "NO_GO" for f in r.facts)
    assert all(f.source_agent == "employee_onboarding" for f in r.facts if hasattr(f, "source_agent"))
    assert all(f.source for f in r.facts)


# ---------- explanation + guard ----------
def test_template_used_without_llm():
    r = run("EMP-007")
    assert r.explanation_source == "template"
    assert "Financial Data Handling and Privacy" in r.explanation


def test_good_llm_rewrite_accepted():
    good = ("You can't start this proposal yet because there is no record of your "
            "Financial Data Handling and Privacy training. Please complete it and run the check again.")
    r = run("EMP-007", llm=lambda s, u: good)
    assert r.explanation_source == "llm" and r.explanation == good


@pytest.mark.parametrize("bad", [
    "You can't proceed. Financial Data Handling and Privacy expired on 2026-01-15.",   # invented date
    "You can't proceed yet. Please finish your pending training.",                      # blocker dropped
    "You're qualified! Financial Data Handling and Privacy is fine.",                  # contradicts decision
])
def test_bad_llm_rewrite_rejected(bad):
    r = run("EMP-007", llm=lambda s, u: bad)
    assert r.explanation_source == "template"
    assert any("rejected" in w for w in r.warnings)


def test_llm_failure_falls_back():
    def boom(s, u):
        raise TimeoutError("endpoint slow")
    r = run("EMP-007", llm=boom)
    assert r.explanation_source == "template" and r.decision == Decision.NO_GO


def test_llm_cannot_change_decision():
    r = run("EMP-014", llm=lambda s, u: "Everything looks great, go ahead.")
    assert r.decision == Decision.NO_GO


# ---------- audit ----------
def test_audit_append_only(env):
    run("EMP-001")
    con = sqlite3.connect(env / "credassure.db")
    row = con.execute("SELECT case_id, actor_role, action, status FROM audit_events").fetchall()
    assert row == [("CASE-T", "onboarding_agent", "readiness_check", "GO")]
    con.close()
    con = sqlite3.connect(env / "credassure.db")
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("DELETE FROM audit_events")
    with pytest.raises(sqlite3.DatabaseError):
        con.execute("UPDATE audit_events SET action='x'")


# ---------- case-intake checklist (guide, Day 5) ----------
ALL_YES = {"business_identity": True, "requested_amount": True,
           "purchase_order": True, "cashflow_data": True}


def test_checklist_complete_and_qualified_is_go():
    r = run_readiness_gate("CASE-T", "EMP-001", as_of=AS_OF, case_checklist=ALL_YES)
    assert r.decision == Decision.GO and r.blockers == []


@pytest.mark.parametrize("item", list(ALL_YES))
def test_any_missing_case_item_is_no_go(item):
    r = run_readiness_gate("CASE-T", "EMP-001", as_of=AS_OF, case_checklist={**ALL_YES, item: False})
    assert r.decision == Decision.NO_GO and r.blockers == [f"CASE:{item.upper()}"]


def test_unanswered_case_item_blocks():
    partial = {k: v for k, v in ALL_YES.items() if k != "purchase_order"}
    r = run_readiness_gate("CASE-T", "EMP-001", as_of=AS_OF, case_checklist=partial)
    assert r.blockers == ["CASE:PURCHASE_ORDER"]


def test_preparer_and_case_blockers_listed_together():
    r = run_readiness_gate("CASE-T", "EMP-007", as_of=AS_OF,
                           case_checklist={**ALL_YES, "cashflow_data": False})
    assert set(r.blockers) == {"TRAINING:FINDATA", "CASE:CASHFLOW_DATA"}
    assert "training" in r.next_action and "case items" in r.next_action


def test_unknown_employee_with_case_gap_still_lists_both():
    r = run_readiness_gate("CASE-T", "EMP-999", as_of=AS_OF,
                           case_checklist={**ALL_YES, "purchase_order": False})
    assert r.decision == Decision.NO_GO
    assert set(r.blockers) == {"EMPLOYEE_FOUND", "CASE:PURCHASE_ORDER"}


# ---------- HR store isolation ----------
def test_tools_are_read_only():
    import readiness.tools as t
    con = t._connect()
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM employees")


# ---------- LangGraph ----------
@pytest.mark.parametrize("emp_id,path_end", [("EMP-001", "working_capital"), ("EMP-007", "paused"),
                                             ("EMP-015", "paused"), ("EMP-999", "paused")])
def test_graph_routing(emp_id, path_end):
    out = build_demo_graph().invoke({"case_id": "CASE-G", "preparer_id": emp_id,
                                     "as_of": AS_OF.isoformat()}, config={"recursion_limit": 10})
    assert path_end in out["log"][-1]


# ---------- eval files ----------
@pytest.mark.parametrize("name,count", [("onboarding_eval.jsonl", 10), ("regression_eval.jsonl", 8)])
def test_eval_set_scores_full_marks(name, count):
    to_api = {"GO": "GO", "NO_GO": "NO-GO", "NEEDS_INPUT": "NEEDS_INPUT", "ERROR": "ERROR"}
    items = [json.loads(l) for l in
             (Path(__file__).parent.parent / "eval" / name).read_text().splitlines() if l]
    assert len(items) == count
    for it in items:
        r = run_readiness_gate(it["input"]["case_id"], it["input"]["employee_id"],
                               as_of=date.fromisoformat(it["input"]["as_of"]),
                               case_checklist=it["input"].get("checklist"))
        assert to_api[r.decision.value] == it["gold"]["decision"], it["id"]
        assert set(r.blockers) == set(it["gold"]["blockers"]), it["id"]
