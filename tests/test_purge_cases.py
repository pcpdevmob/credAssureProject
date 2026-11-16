"""scripts/purge_cases.py removes only the named cases; triggers and audit chain survive."""

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text

from credassure.ledger import migrate, reads, writes
from credassure.ledger.session import case_engine, transaction

SPEC = importlib.util.spec_from_file_location(
    "purge_cases", Path(__file__).parent.parent / "scripts" / "purge_cases.py"
)
assert SPEC and SPEC.loader
purge_cases = importlib.util.module_from_spec(SPEC)
sys.modules["purge_cases"] = purge_cases
SPEC.loader.exec_module(purge_cases)


def _case(s, cid: str) -> None:  # type: ignore[no-untyped-def]
    writes.create_case(
        s, tenant_id="default", case_id=cid, msme_name="Demo", order_ref="PO-1",
        order_value_paise=1, indicative_amount_paise=1, due_date=date(2027, 5, 15),
        preparer_id="u-p",
    )  # fmt: skip
    writes.put_fact(
        s, tenant_id="default", case_id=cid, key="wc.gate", value="GO", unit="",
        source_type="engine", source_ref="t", produced_by="t", input_hash="h", actor="t",
    )  # fmt: skip


def test_purge_removes_only_named_cases_and_keeps_chain(tmp_path: Path) -> None:
    db = tmp_path / "case.db"
    migrate.upgrade("case", db)
    engine = case_engine(db)
    with transaction(engine) as s:
        writes.add_user(
            s, user_id="u-p", tenant_id="default", username="p", role="preparer",
            emp_id=None, password_hash="x",
        )  # fmt: skip
        _case(s, "CA-2026-0001")
        _case(s, "CA-2026-0002")

    with transaction(engine) as s:  # dry run changes nothing
        assert purge_cases.purge(s, ["CA-2026-0002"], dry_run=True)["cases"] == 1
    with transaction(engine) as s:
        counts = purge_cases.purge(s, ["CA-2026-0002"], dry_run=False)
    assert counts["cases"] == 1 and counts["ledger_facts"] == 1

    with transaction(engine) as s:
        assert s.execute(text("SELECT id FROM cases")).scalars().all() == ["CA-2026-0001"]
        assert reads.verify_chain(s) == []
        assert (
            s.execute(
                text("SELECT count(*) FROM audit_log WHERE event_type='CASES_PURGED'")
            ).scalar_one()
            == 1
        )
    with pytest.raises(Exception, match="append-only"), transaction(engine) as s:  # triggers back
        s.execute(text("DELETE FROM ledger_facts"))
