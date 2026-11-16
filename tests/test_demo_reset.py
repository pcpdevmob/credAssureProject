"""scripts/demo_reset.py: same state every run, audited purge, guards, frozen data untouched."""

import hashlib
import importlib.util
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text

from credassure.gateway.settings import Settings
from credassure.ledger import migrate, reads, writes
from credassure.ledger.session import case_engine, transaction

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("demo_reset", ROOT / "scripts" / "demo_reset.py")
assert SPEC and SPEC.loader
demo_reset = importlib.util.module_from_spec(SPEC)
sys.modules["demo_reset"] = demo_reset
SPEC.loader.exec_module(demo_reset)

READ = ("cases/CA-2026-0001", "cases/CA-2026-0013", "offers/CA-2026-0001", "kfs")


def _settings(db: Path, tenant: str = "demo") -> Any:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        jwt_secret="x" * 40,
        case_db=db,
        tenant_id=tenant,
        llm_enabled=False,
        tracing_enabled=False,
        seed_password="fixture-password-123",
    )


def _frozen_hash() -> str:
    h = hashlib.sha256()
    for d in READ:
        for p in sorted((ROOT / "data/frozen/v1" / d).rglob("*")):
            if p.is_file():
                h.update(p.read_bytes())
    return h.hexdigest()


def _purged(db: Path) -> int:
    with transaction(case_engine(db)) as s:
        assert reads.verify_chain(s) == []
        return int(
            s.execute(
                text("SELECT count(*) FROM audit_log WHERE event_type='CASES_PURGED'")
            ).scalar_one()
        )


def _state(views: dict[str, dict[str, Any]]) -> list[tuple[str, str, Any]]:
    return [(c, v["status"], v["route"]) for c, v in views.items()]


def test_demo_reset_is_idempotent_and_audited(tmp_path: Path) -> None:
    db = tmp_path / "case.db"
    # a pre-demo database: users and one case in tenant "default"
    migrate.upgrade("case", db)
    with transaction(case_engine(db)) as s:
        writes.add_user(
            s, user_id="u-old", tenant_id="default", username="old", role="preparer",
            emp_id=None, password_hash="x",
        )  # fmt: skip
        writes.create_case(
            s, tenant_id="default", case_id="CA-2026-0016", msme_name="Old", order_ref="PO",
            order_value_paise=1, indicative_amount_paise=1, due_date=date(2027, 5, 15),
            preparer_id="u-old",
        )  # fmt: skip
    before = _frozen_hash()

    first = demo_reset.main(_settings(db), check_port=False)
    assert list(tmp_path.glob("case.db.bak-*")), "the pre-demo database is backed up"
    with transaction(case_engine(db)) as s:
        assert set(s.execute(text("SELECT DISTINCT tenant_id FROM users")).scalars()) == {"demo"}
        assert set(s.execute(text("SELECT DISTINCT tenant_id FROM cases")).scalars()) == {"demo"}
    assert _state(first) == [
        ("CA-2026-0016", "AWAITING_APPROVAL", "director_finance"),
        ("CA-2026-0017", "PAUSED", None),
    ]
    assert first["CA-2026-0016"]["status"] != "APPROVED"  # never approved by the script
    n = _purged(db)

    second = demo_reset.main(_settings(db), check_port=False)
    assert _state(second) == _state(first)
    assert _purged(db) == n + 1  # one audited purge per rerun, chain intact
    assert _frozen_hash() == before


def test_demo_reset_refuses_e2e_db_and_other_tenant(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="e2e"):
        demo_reset.main(_settings(ROOT / "var" / "case-e2e.db"), check_port=False)
    with pytest.raises(SystemExit, match="TENANT_ID"):
        demo_reset.main(_settings(tmp_path / "case.db", tenant="default"), check_port=False)
    assert not (tmp_path / "case.db").exists()
