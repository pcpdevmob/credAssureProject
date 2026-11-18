"""Scope #38 (NFR-06): online backup is consistent under WAL, restore verifies before replacing."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import backup_db


def _db(path: Path, rows: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS t (n INTEGER)")
    c.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(rows)])
    c.commit()
    c.close()


def _count(path: Path) -> int:
    c = sqlite3.connect(path)
    try:
        return int(c.execute("SELECT count(*) FROM t").fetchone()[0])
    finally:
        c.close()


def test_scope38_backup_then_restore_round_trip(tmp_path: Path) -> None:
    case = tmp_path / "var/case.db"
    _db(case, 5)
    writer = sqlite3.connect(case)  # an open WAL writer, as with a running gateway
    writer.execute("INSERT INTO t VALUES (99)")
    writer.commit()
    out = tmp_path / "var/backups/b1"
    manifest = backup_db.backup(tmp_path, out)
    writer.close()
    assert set(manifest) == {"case.db"}  # missing stores are skipped, not invented
    assert _count(out / "case.db") == 6

    _db(case, 10)  # later changes...
    assert _count(case) == 16
    done = backup_db.restore(tmp_path, out, stamp="T1")
    assert done == ["case.db"]
    assert _count(case) == 6  # ...are rolled back to the backup
    assert _count(tmp_path / "var/backups/pre-restore-T1/case.db") == 16  # and kept


def test_scope38_restore_refuses_a_changed_backup(tmp_path: Path) -> None:
    case = tmp_path / "var/case.db"
    _db(case, 3)
    out = tmp_path / "var/backups/b1"
    backup_db.backup(tmp_path, out)
    _db(out / "case.db", 1)  # tampered after the backup
    _db(case, 4)
    with pytest.raises(SystemExit, match="nothing restored"):
        backup_db.restore(tmp_path, out, stamp="T2")
    assert _count(case) == 7  # untouched


def test_scope38_restore_refuses_paths_outside_the_store_list(tmp_path: Path) -> None:
    _db(tmp_path / "var/case.db", 1)
    out = tmp_path / "var/backups/b1"
    backup_db.backup(tmp_path, out)
    m = json.loads((out / "MANIFEST.json").read_text())
    m["case.db"]["from"] = "../../etc/passwd"
    (out / "MANIFEST.json").write_text(json.dumps(m))
    with pytest.raises(SystemExit, match="unexpected entry"):
        backup_db.restore(tmp_path, out, stamp="T3")


def test_scope38_backup_needs_the_case_db(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="nothing to back up"):
        backup_db.backup(tmp_path, tmp_path / "var/backups/b0")


def test_scope38_restore_refuses_a_store_that_is_open_elsewhere(tmp_path: Path) -> None:
    case = tmp_path / "var/case.db"
    _db(case, 2)
    out = tmp_path / "var/backups/b1"
    backup_db.backup(tmp_path, out)
    _db(case, 3)
    gateway = sqlite3.connect(case)  # an idle pooled connection, as a running gateway holds
    gateway.execute("SELECT count(*) FROM t").fetchone()
    try:
        with pytest.raises(SystemExit, match="in use"):
            backup_db.restore(tmp_path, out, stamp="T4")
    finally:
        gateway.close()
    assert _count(case) == 5  # untouched


def test_scope38_failed_second_store_puts_the_first_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _db(tmp_path / "var/case.db", 2)
    _db(tmp_path / "var/corpus.db", 2)
    out = tmp_path / "var/backups/b1"
    backup_db.backup(tmp_path, out)
    _db(tmp_path / "var/case.db", 5)
    real = backup_db._write_into
    calls = []

    def flaky(src: Path, dest: sqlite3.Connection) -> None:
        calls.append(src.name)
        if len(calls) == 2:  # case.db done, corpus.db fails
            raise OSError("disk full")
        real(src, dest)

    monkeypatch.setattr(backup_db, "_write_into", flaky)
    with pytest.raises(OSError):
        backup_db.restore(tmp_path, out, stamp="T5")
    assert _count(tmp_path / "var/case.db") == 7  # put back, not left at the backup's 2


def test_scope38_backups_are_owner_only(tmp_path: Path) -> None:
    _db(tmp_path / "var/case.db", 1)
    out = tmp_path / "var/backups/b1"
    backup_db.backup(tmp_path, out)
    assert (out.stat().st_mode & 0o777) == 0o700
    assert ((out / "case.db").stat().st_mode & 0o777) == 0o600
