"""Phase 8a: the Supervisor with real adapters (SqlLedger, SqliteSaver on case.db, placeholders).

SUP-01 fixed order end to end, routing to the Director for ₹1.42 cr (APR-02), resume after the
interrupt survives a new Supervisor instance (checkpoint on disk), and the audit chain verifies.
"""

import sqlite3
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from credassure.agents.critic import agent as critic
from credassure.agents.lendwise import agent as lendwise
from credassure.agents.onboarding import agent as onboarding
from credassure.agents.supervisor.graph import Supervisor
from credassure.agents.working_capital import agent as working_capital
from credassure.core.enums import AgentName, Stage
from credassure.engines.onboarding_rules import evaluate
from credassure.ledger import migrate, reads, session, writes
from credassure.ledger.store import SqlLedger
from credassure.llm.fake import FakeLLM
from credassure.tools.runner import ToolRunner

CASE, T = "CA-2026-0001", "default"
GO_PROFILE = {  # an authorised preparer with every rule current (Phase 9a real onboarding agent)
    "emp_id": "E001",
    "role": "senior_finance_analyst",
    "trainings": [
        {"code": c, "status": "completed", "expires_on": "2027-07-18"}
        for c in ("AML-201", "DPDP-101", "FIN-101")
    ],
    "policy_ack_version": "v3",
}
ONB_TOOLS = {
    "get_hr_profile": lambda case_id: GO_PROFILE,
    "evaluate_onboarding_rules": lambda case_id, profile: evaluate(profile, date(2026, 11, 15)),
}


class _Clock:
    def today(self) -> date:
        return date(2026, 11, 15)


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Path]:
    path = tmp_path / "case.db"
    migrate.upgrade("case", path)
    engine = session.case_engine(path)
    with session.transaction(engine) as s:
        writes.add_user(
            s, user_id="u-prep", tenant_id=T, username="prep", role="preparer", password_hash="x"
        )
        writes.create_case(
            s,
            tenant_id=T,
            case_id=CASE,
            msme_name="Demo Electronics",
            order_ref="PO-1",
            order_value_paise=3_20_00_000_00,
            indicative_amount_paise=2_00_00_000_00,
            due_date=date(2027, 5, 15),
            preparer_id="u-prep",
        )
    engine.dispose()
    yield path


def _supervisor(db: Path, llm: FakeLLM | None) -> tuple[Supervisor, Any]:
    engine = session.case_engine(db)
    ledger = SqlLedger(engine, T)
    saver = SqliteSaver(sqlite3.connect(db, check_same_thread=False))
    sup = Supervisor(
        agents={
            Stage.ONBOARDING: onboarding.run,
            Stage.WORKING_CAPITAL: working_capital.run,
            Stage.LENDWISE: lendwise.run,
            Stage.CRITIC: critic.run,
        },
        store=ledger,
        ledger=ledger,
        tools=lambda agent: ToolRunner(agent, ONB_TOOLS if agent is AgentName.ONBOARDING else {}),
        llm=llm,
        clock=_Clock(),
        checkpointer=saver,
        tenant_id=T,
    )
    return sup, engine


@pytest.mark.parametrize("llm_enabled", [True, False])
def test_SUP01_placeholders_run_to_the_director_and_resume_from_disk(
    db: Path, llm_enabled: bool
) -> None:
    llm = FakeLLM() if llm_enabled else None
    sup, engine = _supervisor(db, llm)
    outcome = sup.run(CASE)
    assert outcome.status == "AWAITING_APPROVAL"
    assert list(outcome.results) == [
        Stage.ONBOARDING,
        Stage.WORKING_CAPITAL,
        Stage.LENDWISE,
        Stage.CRITIC,
    ]
    with session.transaction(engine) as s:
        case = reads.get_case(s, T, CASE)
        assert case is not None and case.route == "director_finance"
        assert reads.verify_chain(s) == []
    # onboarding GO needs no explanation, so its model call is skipped (Phase 9a)
    assert (llm is not None and len(llm.calls) >= 3) or (llm is None)

    # A fresh Supervisor (new process after a restart) resumes the same interrupt from case.db.
    again, _ = _supervisor(db, llm)
    assert again.run(CASE).status == "AWAITING_APPROVAL"  # waiting: nothing re-runs
    assert again.decide(CASE, decision="approve").status == "APPROVED"


def test_scope4_tool_runner_is_built_per_stage_for_that_agent(db: Path) -> None:
    seen: list[AgentName] = []
    sup, _ = _supervisor(db, None)
    real = sup.tools
    sup.tools = lambda agent: (seen.append(agent), real(agent))[1]
    sup.run(CASE)
    assert seen == [
        AgentName.ONBOARDING,
        AgentName.WORKING_CAPITAL,
        AgentName.LENDWISE,
        AgentName.CRITIC,
    ]
