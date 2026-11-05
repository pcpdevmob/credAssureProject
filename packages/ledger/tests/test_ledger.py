"""Phase 5: case.db schema, fact ledger, hash-chained audit, run lock, hr.db read-only, migrations.

Scope #22 (WAL, busy timeout, one run per case), #27 (tenant_id), #29 (Alembic up/down),
#49 (fact + audit in one transaction, row_version); OBJ-08 (tamper-evident); ONB-05 (HR read-only);
APR-04/05; SUP-08.
"""

import sqlite3
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import DBAPIError

from credassure.ledger import migrate, models, reads, session, writes

T = "default"


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    db = tmp_path / "case.db"
    migrate.upgrade("case", db)
    eng = session.case_engine(db)
    with session.transaction(eng) as s:
        writes.add_user(
            s, user_id="u-prep", tenant_id=T, username="prep", role="preparer", password_hash="x"
        )
        writes.add_user(
            s,
            user_id="u-dir",
            tenant_id=T,
            username="dir",
            role="director_finance",
            password_hash="x",
        )
        writes.create_case(
            s,
            tenant_id=T,
            case_id="CA-2026-0001",
            msme_name="Demo Electronics",
            order_ref="PO-1",
            order_value_paise=3_20_00_000_00,
            indicative_amount_paise=2_00_00_000_00,
            due_date=date(2027, 5, 15),
            preparer_id="u-prep",
        )
        writes.add_user(
            s, user_id="u-vp", tenant_id=T, username="vp", role="vp_finance", password_hash="x"
        )
        writes.route_case(
            s, tenant_id=T, case_id="CA-2026-0001", route="director_finance", actor="supervisor"
        )
    yield eng  # case is AWAITING_APPROVAL for the director at row_version 2
    eng.dispose()


def _put(
    s: object, key: str = "wc.recommended_amount", value: object = Decimal("14200000")
) -> models.LedgerFact:
    return writes.put_fact(
        s,  # type: ignore[arg-type]
        tenant_id=T,
        case_id="CA-2026-0001",
        key=key,
        value=value,  # type: ignore[arg-type]
        unit="INR",
        source_type="engine",
        source_ref="cashflow.recommend",
        produced_by="engines@54cf000",
        input_hash="abc",
        actor="supervisor",
    )


def test_scope22_wal_busy_timeout_and_foreign_keys(engine: Engine) -> None:
    with engine.connect() as c:
        assert c.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert c.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
        assert c.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1


def test_scope22_one_active_run_per_case(engine: Engine) -> None:
    with (
        session.run_lock(engine, T, "CA-2026-0001", "run-1"),
        pytest.raises(session.RunInProgressError),
        session.run_lock(engine, T, "CA-2026-0001", "run-2"),
    ):
        pass
    with session.run_lock(engine, T, "CA-2026-0001", "run-3"):  # released after the first run
        pass


def test_scope27_every_case_scoped_table_has_tenant_id() -> None:
    global_tables = {"prompt_registry", "eval_runs", "eval_results"}
    for table in models.CaseBase.metadata.tables.values():
        if table.name not in global_tables:
            assert "tenant_id" in table.c, table.name


def test_OBJ08_fact_versions_append_and_latest_wins(engine: Engine) -> None:
    with session.transaction(engine) as s:
        assert _put(s).version == 1
        assert _put(s, value=Decimal("15000000")).version == 2
    with session.transaction(engine) as s:
        latest = reads.get_latest(s, T, "CA-2026-0001", "wc.recommended_amount")
        assert latest is not None and (latest.version, latest.value_text) == (2, "15000000")
        assert reads.get_latest(s, "tenant-2", "CA-2026-0001", "wc.recommended_amount") is None
        assert [f.version for f in reads.list_for_case(s, T, "CA-2026-0001")] == [1, 2]


def test_BR05_fact_values_are_never_float(engine: Engine) -> None:
    with session.transaction(engine) as s, pytest.raises(TypeError):
        _put(s, value=0.1)


def test_scope49_fact_and_its_audit_event_commit_together(engine: Engine) -> None:
    with session.transaction(engine) as s:
        fact = _put(s)
    with session.transaction(engine) as s:
        events = reads.audit_events(s, T, "CA-2026-0001")
        assert [e.event_type for e in events] == ["CASE_CREATED", "ROUTED", "FACT_WRITTEN"]
        assert events[-1].payload["key"] == fact.key


def test_scope49_failed_audit_rolls_back_the_fact(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_: object, **__: object) -> None:
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr(writes, "append_audit", boom)
    with pytest.raises(RuntimeError), session.transaction(engine) as s:
        _put(s)
    with session.transaction(engine) as s:
        assert reads.list_for_case(s, T, "CA-2026-0001") == []


@pytest.mark.parametrize("table", ["audit_log", "ledger_facts", "approvals"])
def test_OBJ08_append_only_tables_reject_update_and_delete(engine: Engine, table: str) -> None:
    with session.transaction(engine) as s:
        _put(s)
        writes.record_decision(
            s,
            tenant_id=T,
            case_id="CA-2026-0001",
            approver_id="u-dir",
            role="director_finance",
            expected_version=2,
            decision="return",
            return_stage="lendwise",
            comment="check fees",
        )
    for sql in (f"UPDATE {table} SET tenant_id = 'x'", f"DELETE FROM {table}"):  # noqa: S608 - fixed names
        with pytest.raises(DBAPIError, match="append-only"), session.transaction(engine) as s:
            s.execute(text(sql))


def test_OBJ08_verify_chain_detects_tampering(engine: Engine, tmp_path: Path) -> None:
    with session.transaction(engine) as s:
        _put(s)
        _put(s, key="wc.peak_week", value=9)
        assert reads.verify_chain(s) == []
    engine.dispose()
    raw = sqlite3.connect(tmp_path / "case.db")  # an attacker with file access drops the trigger
    raw.execute("DROP TRIGGER audit_log_no_update")
    raw.execute(
        "UPDATE audit_log SET payload_json = replace(payload_json, '14200000', '1') WHERE seq = 3"
    )
    raw.commit()
    raw.close()
    with session.transaction(engine) as s:
        assert reads.verify_chain(s) == [3]


def test_APR04_decision_is_recorded_with_audit_and_bumps_row_version(engine: Engine) -> None:
    with session.transaction(engine) as s:
        writes.record_decision(
            s,
            tenant_id=T,
            case_id="CA-2026-0001",
            approver_id="u-dir",
            role="director_finance",
            expected_version=2,
            decision="approve",
            return_stage=None,
            comment="ok",
        )
    with session.transaction(engine) as s:
        case = reads.get_case(s, T, "CA-2026-0001")
        assert case is not None and (case.status, case.row_version) == ("APPROVED", 3)
        assert reads.audit_events(s, T, "CA-2026-0001")[-1].event_type == "DECISION_RECORDED"


def test_scope49_stale_row_version_is_a_conflict(engine: Engine) -> None:
    """The approver decided on version 1; the case has since moved on (routed again, version 2)."""
    with pytest.raises(writes.ConflictError, match="version"), session.transaction(engine) as s:
        writes.record_decision(
            s,
            tenant_id=T,
            case_id="CA-2026-0001",
            approver_id="u-dir",
            role="director_finance",
            expected_version=1,
            decision="approve",
            return_stage=None,
            comment="",
        )


def test_APR04_a_decided_case_cannot_be_decided_again(engine: Engine) -> None:
    decide = dict(
        tenant_id=T,
        case_id="CA-2026-0001",
        approver_id="u-dir",
        role="director_finance",
        return_stage=None,
        comment="",
    )
    with session.transaction(engine) as s:
        writes.record_decision(s, expected_version=2, decision="approve", **decide)  # type: ignore[arg-type]
    with pytest.raises(writes.ConflictError, match="APPROVED"), session.transaction(engine) as s:
        writes.record_decision(s, expected_version=3, decision="reject", **decide)  # type: ignore[arg-type]


def test_APR05_role_must_match_the_user_and_the_route(engine: Engine) -> None:
    base = dict(
        tenant_id=T,
        case_id="CA-2026-0001",
        expected_version=2,
        decision="approve",
        return_stage=None,
        comment="",
    )
    with (
        pytest.raises(writes.ConflictError, match="is director_finance"),
        session.transaction(engine) as s,
    ):
        writes.record_decision(s, approver_id="u-dir", role="vp_finance", **base)  # type: ignore[arg-type]
    with pytest.raises(writes.ConflictError, match="routed to"), session.transaction(engine) as s:
        writes.record_decision(s, approver_id="u-vp", role="vp_finance", **base)  # type: ignore[arg-type]


def test_APR05_ledger_refuses_self_approval_as_defence_in_depth(engine: Engine) -> None:
    with pytest.raises(writes.ConflictError, match="own case"), session.transaction(engine) as s:
        writes.record_decision(
            s,
            tenant_id=T,
            case_id="CA-2026-0001",
            approver_id="u-prep",
            role="director_finance",
            expected_version=2,
            decision="approve",
            return_stage=None,
            comment="",
        )


def test_SUP08_reads_are_scoped_to_tenant_and_case(engine: Engine) -> None:
    with session.transaction(engine) as s:
        _put(s)
        assert reads.get_case(s, "tenant-2", "CA-2026-0001") is None
        assert reads.list_for_case(s, "tenant-2", "CA-2026-0001") == []
        assert reads.list_for_case(s, T, "CA-2026-0002") == []


def test_ONB05_hr_db_is_read_only(tmp_path: Path) -> None:
    db = tmp_path / "hr.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE employees (emp_id TEXT PRIMARY KEY, role TEXT)")
    con.execute("INSERT INTO employees VALUES ('E001', 'credit_proposal_officer')")
    con.commit()
    con.close()
    hr = session.hr_engine(db)
    with hr.connect() as c:
        assert c.execute(text("SELECT role FROM employees")).scalar() == "credit_proposal_officer"
        with pytest.raises(DBAPIError, match=r"readonly|read-only"):
            c.execute(text("UPDATE employees SET role = 'x'"))
    hr.dispose()


@pytest.mark.parametrize("which", ["case", "corpus"])
def test_scope29_migrations_upgrade_downgrade_upgrade(tmp_path: Path, which: str) -> None:
    db = tmp_path / f"{which}.db"
    migrate.upgrade(which, db)
    first = set(inspect(session.case_engine(db)).get_table_names())
    assert ("audit_log" if which == "case" else "chunks") in first
    migrate.downgrade(which, db)
    assert set(inspect(session.case_engine(db)).get_table_names()) <= {"alembic_version"}
    migrate.upgrade(which, db)
    assert set(inspect(session.case_engine(db)).get_table_names()) == first


def test_scope29_corpus_db_has_fts5_keyword_index(tmp_path: Path) -> None:
    db = tmp_path / "corpus.db"
    migrate.upgrade("corpus", db)
    with session.case_engine(db).connect() as c:
        c.exec_driver_sql(
            "INSERT INTO documents (doc_id, title, collection, jurisdiction, applies_to) "
            "VALUES ('D', 't', 'public', 'IN', 'all')"
        )
        c.exec_driver_sql(
            "INSERT INTO chunks (chunk_id, doc_id, strategy, ordinal, text, injection_flag) "
            "VALUES ('D#0', 'D', 'section', 0, 'annual guarantee fee on outstanding', 0)"
        )
        c.exec_driver_sql("INSERT INTO chunks_fts (chunks_fts) VALUES ('rebuild')")
        hit = c.exec_driver_sql(
            "SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH 'guarantee'"
        ).scalar()
        assert hit is not None


def test_S08_seed_creates_users_with_argon2_hashes_and_is_idempotent(tmp_path: Path) -> None:
    from credassure.ledger import seed
    from credassure.security.auth import verify_password

    db = tmp_path / "case.db"
    with pytest.raises(SystemExit, match="SEED_PASSWORD"):
        seed.seed(db, {})
    with pytest.raises(SystemExit) as short:
        seed.seed(db, {"SEED_PASSWORD": "short-pw"})
    message = str(short.value)
    assert "SEED_PASSWORD" in message and "12" in message
    assert "short-pw" not in message  # the value is never echoed
    env = {"SEED_PASSWORD": "demo-pass-0001", "SEED_PASSWORD_DEMO_VP": "vp-pass-00002"}
    assert seed.seed(db, env) == 25
    assert seed.seed(db, env) == 0
    with session.transaction(session.case_engine(db)) as s:
        users = {u.username: u for u in s.scalars(select(models.User))}
    assert users["demo.director"].role == "director_finance"
    assert users["demo.preparer"].emp_id == "E001"
    assert verify_password(users["demo.vp"].password_hash, "vp-pass-00002")
    assert verify_password(users["prep.e005"].password_hash, "demo-pass-0001")
    assert "demo-pass-0001" not in (tmp_path / "case.db").read_bytes().decode("latin-1")


def test_scope22_a_stale_lock_from_a_crashed_run_is_taken_over(engine: Engine) -> None:
    from datetime import UTC, datetime, timedelta

    with session.transaction(engine) as s:
        s.add(
            models.RunLock(
                case_id="CA-2026-0001",
                tenant_id=T,
                run_id="dead",
                acquired_at=datetime.now(UTC) - timedelta(minutes=6),
            )
        )
    with session.run_lock(engine, T, "CA-2026-0001", "run-new"):
        pass


def test_APR04_a_final_decision_cannot_be_reopened_by_rerouting(engine: Engine) -> None:
    with session.transaction(engine) as s:
        writes.record_decision(
            s,
            tenant_id=T,
            case_id="CA-2026-0001",
            approver_id="u-dir",
            role="director_finance",
            expected_version=2,
            decision="reject",
            return_stage=None,
            comment="",
        )
    with pytest.raises(writes.ConflictError, match="REJECTED"), session.transaction(engine) as s:
        writes.route_case(s, tenant_id=T, case_id="CA-2026-0001", route="vp_finance", actor="x")
