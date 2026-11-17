"""Phase 8 ledger additions: audit head (OBJ-08), run-lock heartbeat (scope #22), jobs (scope #47),
migration up/down (scope #29) and the SqlLedger adapter (LedgerPort + SupervisorStore, SUP-08).
"""

import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, select, update

from credassure.core.enums import AgentName, Decision, Stage
from credassure.core.results import AgentResult
from credassure.ledger import migrate, models, reads, session, writes
from credassure.ledger.store import SqlLedger

T = "default"
CASE = "CA-2026-0001"


@pytest.fixture
def db(tmp_path: Path) -> Path:
    return tmp_path / "case.db"


@pytest.fixture
def engine(db: Path) -> Iterator[Engine]:
    migrate.upgrade("case", db)
    eng = session.case_engine(db)
    with session.transaction(eng) as s:
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
    yield eng  # case is CREATED, not routed
    eng.dispose()


def _put(s: object, key: str, value: object) -> None:
    writes.put_fact(
        s,  # type: ignore[arg-type]
        tenant_id=T,
        case_id=CASE,
        key=key,
        value=value,  # type: ignore[arg-type]
        unit="INR",
        source_type="engine",
        source_ref="cashflow.recommend",
        produced_by="engines@test",
        input_hash="abc",
        actor="supervisor",
    )


def _lock_age(engine: Engine) -> timedelta:
    with session.transaction(engine) as s:
        acquired = s.scalar(
            select(models.RunLock.acquired_at).where(models.RunLock.case_id == CASE)
        )
    assert acquired is not None
    return datetime.now(UTC).replace(tzinfo=None) - acquired.replace(tzinfo=None)


def _backdate_lock(engine: Engine, run_id: str, seconds: int) -> None:
    with session.transaction(engine) as s:
        s.add(
            models.RunLock(
                case_id=CASE,
                tenant_id=T,
                run_id=run_id,
                acquired_at=datetime.now(UTC) - timedelta(seconds=seconds),
            )
        )


# --- audit head (OBJ-08) -----------------------------------------------------------------------


def test_OBJ08_audit_head_tracks_the_last_audit_row(engine: Engine) -> None:
    with session.transaction(engine) as s:
        _put(s, "wc.recommended_amount", Decimal("14200000"))
        _put(s, "wc.peak_week", 9)
        _put(s, "wc.peak_shortfall", Decimal("16200000"))
    with session.transaction(engine) as s:
        last = s.scalars(select(models.AuditLog).order_by(models.AuditLog.seq.desc())).first()
        head = reads.audit_head(s, T)
        assert last is not None and head is not None
        assert (head.seq, head.hash) == (last.seq, last.hash)


def test_OBJ08_truncated_audit_tail_is_detected(engine: Engine, db: Path) -> None:
    with session.transaction(engine) as s:
        _put(s, "wc.recommended_amount", Decimal("14200000"))
        _put(s, "wc.peak_week", 9)
        assert reads.verify_chain(s) == []
    engine.dispose()
    raw = sqlite3.connect(db)  # an attacker with file access drops the triggers and cuts the tail
    triggers = raw.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='audit_log'"
    ).fetchall()
    for (name,) in triggers:
        raw.execute(f'DROP TRIGGER "{name}"')
    raw.execute("DELETE FROM audit_log WHERE seq=(SELECT max(seq) FROM audit_log)")
    raw.commit()
    raw.close()
    with session.transaction(engine) as s:
        assert reads.verify_chain(s) != []


# --- run lock heartbeat (scope #22) ------------------------------------------------------------


def test_scope22_stale_lock_is_three_heartbeats_of_thirty_seconds() -> None:
    assert timedelta(seconds=30) == session.HEARTBEAT
    assert session.STALE_LOCK == 3 * session.HEARTBEAT == timedelta(seconds=90)


def test_scope22_heartbeat_refreshes_a_held_lock(engine: Engine) -> None:
    with session.run_lock(engine, T, CASE, "run-1"):
        with session.transaction(engine) as s:
            s.execute(
                update(models.RunLock)
                .where(models.RunLock.case_id == CASE)
                .values(acquired_at=datetime.now(UTC) - timedelta(seconds=60))
            )
        assert _lock_age(engine) >= timedelta(seconds=59)
        assert session.heartbeat(engine, CASE, "run-1") is True
        assert _lock_age(engine) < timedelta(seconds=10)


def test_scope22_lock_younger_than_stale_is_not_taken_over(engine: Engine) -> None:
    _backdate_lock(engine, "alive", 89)
    with pytest.raises(session.RunInProgressError), session.run_lock(engine, T, CASE, "new"):
        pass


def test_scope22_lock_older_than_stale_is_taken_over_and_old_heartbeat_fails(
    engine: Engine,
) -> None:
    _backdate_lock(engine, "dead", 91)
    with session.run_lock(engine, T, CASE, "new"):
        assert session.heartbeat(engine, CASE, "dead") is False
        assert session.heartbeat(engine, CASE, "new") is True


# --- jobs (scope #47) --------------------------------------------------------------------------


def _job(s: object, key: str | None) -> models.Job:
    return writes.create_job(
        s,  # type: ignore[arg-type]
        tenant_id=T,
        case_id=CASE,
        kind="run",
        stage=None,
        idempotency_key=key,
        actor="u-prep",
    )


def test_scope47_same_idempotency_key_returns_the_same_job(engine: Engine) -> None:
    with session.transaction(engine) as s:
        first = _job(s, "key-1").id
    with session.transaction(engine) as s:
        assert _job(s, "key-1").id == first
        assert _job(s, "key-2").id != first


def test_scope47_update_job_sets_status_and_outcome(engine: Engine) -> None:
    with session.transaction(engine) as s:
        job_id = _job(s, "key-1").id
    with session.transaction(engine) as s:
        writes.update_job(s, job_id, status="succeeded", outcome="AWAITING_APPROVAL")
    with session.transaction(engine) as s:
        job = s.get(models.Job, job_id)
        assert job is not None
        assert (job.status, job.outcome, job.error) == ("succeeded", "AWAITING_APPROVAL", None)
    with session.transaction(engine) as s:
        writes.update_job(s, job_id, status="failed", error="stage timeout")
    with session.transaction(engine) as s:
        job = s.get(models.Job, job_id)
        assert job is not None and (job.status, job.error) == ("failed", "stage timeout")


# --- migrations (scope #29) --------------------------------------------------------------------


def test_scope29_phase8_migration_downgrades_one_step_and_upgrades_again(db: Path) -> None:
    migrate.upgrade("case", db)
    head = set(inspect(session.case_engine(db)).get_table_names())
    assert {"jobs", "audit_head"} <= head
    migrate.downgrade("case", db, "37bd7037b99d")
    previous = set(inspect(session.case_engine(db)).get_table_names())
    assert "jobs" not in previous and "audit_head" not in previous
    assert "audit_log" in previous
    migrate.upgrade("case", db)
    assert set(inspect(session.case_engine(db)).get_table_names()) == head


# --- SqlLedger adapter -------------------------------------------------------------------------


def _result(decision: Decision = Decision.GO) -> AgentResult:
    return AgentResult(
        agent=AgentName.WORKING_CAPITAL,
        case_id=CASE,
        stage=Stage.WORKING_CAPITAL,
        decision=decision,
        trace_id="trace-wc-1",
        agent_version="0.0.1-test",
    )


def test_OBJ08_sql_ledger_put_fact_and_get_round_trip(engine: Engine) -> None:
    ledger = SqlLedger(engine, T)
    v1 = ledger.put_fact(
        CASE,
        "wc.recommended_amount",
        Decimal("14200000"),
        unit="INR",
        source_type="engine",
        source_ref="cashflow.recommend",
        produced_by="working_capital@0.1.0",
    )
    assert v1 == 1
    assert ledger.get(CASE, "wc.recommended_amount") == "14200000"
    v2 = ledger.put_fact(
        CASE,
        "wc.recommended_amount",
        Decimal("15000000"),
        unit="INR",
        source_type="engine",
        source_ref="cashflow.recommend",
        produced_by="working_capital@0.1.0",
    )
    assert v2 == 2
    assert ledger.get(CASE, "wc.recommended_amount") == "15000000"
    assert ledger.get(CASE, "wc.missing") is None
    with session.transaction(engine) as s:
        fact = reads.get_latest(s, T, CASE, "wc.recommended_amount")
        assert fact is not None
        assert (fact.source_type, fact.source_ref) == ("engine", "cashflow.recommend")
        assert len(fact.input_hash) == 64  # sha256 hex of the value


def test_SUP08_sql_ledger_is_bound_to_its_tenant(engine: Engine) -> None:
    SqlLedger(engine, T).put_fact(
        CASE,
        "wc.peak_week",
        9,
        unit="week",
        source_type="engine",
        source_ref="cashflow.table",
        produced_by="working_capital@0.1.0",
    )
    assert SqlLedger(engine, "tenant-2").get(CASE, "wc.peak_week") is None


def test_SUP06_stage_started_numbers_attempts(engine: Engine) -> None:
    store = SqlLedger(engine, T)
    first = store.stage_started(CASE, Stage.WORKING_CAPITAL.value, "trace-1")
    second = store.stage_started(CASE, Stage.WORKING_CAPITAL.value, "trace-2")
    assert first != second
    with session.transaction(engine) as s:
        attempts = {r.id: r.attempt for r in s.scalars(select(models.StageRun))}
    assert (attempts[first], attempts[second]) == (1, 2)


def test_SUP04_stage_finished_stores_decision_and_result(engine: Engine) -> None:
    store = SqlLedger(engine, T)
    run_id = store.stage_started(CASE, Stage.WORKING_CAPITAL.value, "trace-wc-1")
    store.stage_finished(run_id, _result(Decision.NEEDS_INPUT))
    with session.transaction(engine) as s:
        run = s.get(models.StageRun, run_id)
        assert run is not None
        assert run.decision == "NEEDS_INPUT"
        assert run.result_json is not None
        assert json.loads(run.result_json)["decision"] == "NEEDS_INPUT"
        assert run.trace_id == "trace-wc-1"
        assert run.ended_at is not None
        events = [e.event_type for e in reads.audit_events(s, T, CASE)]
        assert "STAGE_COMPLETED" in events
        assert reads.verify_chain(s) == []


def test_SUP06_set_state_updates_case_status_and_stage(engine: Engine) -> None:
    SqlLedger(engine, T).set_state(CASE, status="PAUSED", current_stage="working_capital")
    with session.transaction(engine) as s:
        case = reads.get_case(s, T, CASE)
        assert case is not None
        assert (case.status, case.current_stage) == ("PAUSED", "working_capital")


def test_SUP05_store_audit_appends_to_the_chain(engine: Engine) -> None:
    SqlLedger(engine, T).audit(CASE, "GATE_OVERRIDE", {"stage": "working_capital"})
    with session.transaction(engine) as s:
        events = reads.audit_events(s, T, CASE)
        assert events[-1].event_type == "GATE_OVERRIDE"
        assert reads.verify_chain(s) == []


def test_APR02_store_route_awaits_the_director(engine: Engine) -> None:
    SqlLedger(engine, T).route(CASE, "director_finance")
    with session.transaction(engine) as s:
        case = reads.get_case(s, T, CASE)
        assert case is not None
        assert (case.status, case.route) == ("AWAITING_APPROVAL", "director_finance")


# --- ADR 0023: offer tables dropped (Phase 10b, scope #29) ---------------------------------------

OFFER_TABLES = {"offers", "offer_evaluations", "negotiation_messages"}


def test_scope29_ADR0023_offer_tables_drop_up_down_up(db: Path) -> None:
    migrate.upgrade("case", db)
    assert not OFFER_TABLES & set(inspect(session.case_engine(db)).get_table_names())
    migrate.downgrade("case", db, "-1")
    restored = set(inspect(session.case_engine(db)).get_table_names())
    assert restored >= OFFER_TABLES
    with sqlite3.connect(db) as conn:  # recreated empty
        assert all(
            conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] == 0  # noqa: S608
            for t in OFFER_TABLES
        )
    migrate.upgrade("case", db)
    assert not OFFER_TABLES & set(inspect(session.case_engine(db)).get_table_names())


def test_scope29_ADR0023_offer_table_drop_refuses_a_non_empty_table(db: Path) -> None:
    migrate.upgrade("case", db)
    migrate.downgrade("case", db, "-1")
    eng = session.case_engine(db)
    with session.transaction(eng) as s:
        writes.add_user(
            s, user_id="u", tenant_id=T, username="u", role="preparer", password_hash="x"
        )
        writes.create_case(
            s,
            tenant_id=T,
            case_id=CASE,
            msme_name="m",
            order_ref="o",
            order_value_paise=1,
            indicative_amount_paise=1,
            due_date=date(2026, 12, 1),
            preparer_id="u",
        )
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO negotiation_messages (tenant_id, case_id, offer_id, round, template_id, "
            "slots_json, rendered_text, created_at) "
            "VALUES (?, ?, 'O1', 1, 't', '{}', 'x', '2026-11-17')",
            (T, CASE),
        )
    with pytest.raises(Exception, match="not empty"):
        migrate.upgrade("case", db)
    assert set(inspect(session.case_engine(db)).get_table_names()) >= OFFER_TABLES  # untouched


# --- own-KFS lineage refs carry the tenant term (Phase 10b item 3, SUP-08, BR-14) ---------------


def test_SUP08_corpus_refs_own_kfs_requires_the_same_tenant(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.db"
    migrate.upgrade("corpus", corpus)
    eng = session.case_engine(corpus)
    with session.transaction(eng) as s:
        s.add(
            models.Document(
                doc_id="KFS-9", title="k", collection="kfs", sha256="abc",
                case_id="CA-2026-0001", tenant_id="demo",
            )
        )  # fmt: skip
        s.flush()
        s.add(models.Chunk(chunk_id="KFS-9#section#0", doc_id="KFS-9", strategy="section",
                           ordinal=0, text="t"))  # fmt: skip
    own = frozenset({"KFS-9@abc"})
    with session.transaction(eng) as s:
        mine = reads.corpus_refs(s, ["KFS-9#section#0"], "demo", "CA-2026-0016", own)
        other = reads.corpus_refs(s, ["KFS-9#section#0"], "acme", "CA-2026-0016", own)
    assert set(mine) == {"KFS-9#section#0"}
    assert other == {}
