"""Backup and restore of the SQLite stores (scope #38, NFR-06).

    make backup                          # var/backups/<UTC time>/ + MANIFEST.json
    make restore FROM=var/backups/<dir>  # stop the gateway first; keeps a pre-restore copy

Uses SQLite's online backup API, so a backup taken while the gateway runs is consistent (WAL
included). Each copy is checked with PRAGMA integrity_check and recorded with its SHA-256. A
restore checks every hash and integrity again before it replaces anything, and the current files
go to var/backups/pre-restore-<time>/ first, so a restore can itself be undone. A restore refuses
to run while another process (the gateway) has a store open, and puts back any store it already
replaced if a later one fails. For case.db the audit hash chain must also verify (OBJ-08).

Backed up: case.db (cases, ledger, append-only audit), corpus.db (the ingested library) and
llm_cache.db (recorded model replies for REPLAY_MODE). Not backed up: hr.db (rebuilt from frozen
data by `make hr-db`) and Chroma (rebuilt by `make ingest`).
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORES = {
    "case.db": "var/case.db",
    "corpus.db": "var/corpus.db",
    "llm_cache.db": "var/llm_cache.db",
}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _copy(src: Path, dst: Path) -> None:
    """SQLite online backup: consistent even while another process writes."""
    # Not mode=ro: a WAL reader needs the -shm file. The backup API only reads the source.
    s, d = sqlite3.connect(src), sqlite3.connect(dst)
    try:
        s.backup(d)
    finally:
        s.close()
        d.close()
    d = sqlite3.connect(dst)
    try:
        d.execute("PRAGMA journal_mode=DELETE")  # one self-contained file, no -wal sidecar
    finally:
        d.close()


def _ok(path: Path) -> bool:
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return bool(c.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
    finally:
        c.close()  # sqlite3's context manager commits but never closes


def backup(root: Path, out: Path) -> dict[str, dict[str, str]]:
    out.mkdir(mode=0o700, parents=True, exist_ok=False)  # case data and the audit log
    manifest: dict[str, dict[str, str]] = {}
    for name, rel in STORES.items():
        src = root / rel
        if not src.exists():
            continue
        dst = out / name
        _copy(src, dst)
        os.chmod(dst, 0o600)
        if not _ok(dst):
            raise SystemExit(f"backup of {name} failed integrity_check")
        manifest[name] = {"from": rel, "sha256": _sha(dst)}
    if "case.db" not in manifest:
        raise SystemExit(f"nothing to back up: {root / STORES['case.db']} does not exist")
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _chain_ok(path: Path) -> bool:
    """case.db only: the audit hash chain still verifies (OBJ-08). Catches a data file edited
    together with its MANIFEST hash, which the hash check alone cannot."""
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        has_audit = c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit_log'"
        ).fetchone()
    finally:
        c.close()
    if not has_audit:
        return True
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from credassure.ledger.reads import verify_chain

    engine = create_engine(f"sqlite:///file:{path}?mode=ro&uri=true")
    try:
        with Session(engine) as session:
            return verify_chain(session) == []
    finally:
        engine.dispose()


def _claim(target: Path) -> sqlite3.Connection:
    """Open the live store with no wait and leave WAL mode. SQLite refuses that while any other
    connection (a running gateway's pool) has the file open, so a live database is never
    overwritten. The returned connection is the restore destination."""
    conn = sqlite3.connect(target, timeout=0, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=DELETE").fetchone()
    except sqlite3.OperationalError as exc:
        conn.close()
        raise SystemExit(f"{target} is in use; stop make run-api first. Nothing restored.") from exc
    return conn


def _write_into(src: Path, dest: sqlite3.Connection) -> None:
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        s.backup(dest)  # one step: the destination changes completely or not at all
    finally:
        s.close()


def restore(root: Path, src: Path, *, stamp: str) -> list[str]:
    manifest: dict[str, dict[str, str]] = json.loads((src / "MANIFEST.json").read_text())
    for name, meta in manifest.items():  # verify everything before touching anything
        if name not in STORES or meta.get("from") != STORES[name]:
            raise SystemExit(f"unexpected entry {name!r} in {src / 'MANIFEST.json'}")
        f = src / name
        if not f.exists() or _sha(f) != meta["sha256"] or not _ok(f) or not _chain_ok(f):
            raise SystemExit(f"{f} is missing, changed or corrupt; nothing restored")
    targets = {name: root / meta["from"] for name, meta in manifest.items()}
    claimed: dict[str, sqlite3.Connection] = {}
    try:
        for name, target in targets.items():  # every live store free, before any write
            if target.exists():
                claimed[name] = _claim(target)
        keep = root / "var/backups" / f"pre-restore-{stamp}"
        for name, conn in claimed.items():
            keep.mkdir(mode=0o700, parents=True, exist_ok=True)
            k = sqlite3.connect(keep / name)
            try:
                conn.backup(k)
            finally:
                k.close()
            os.chmod(keep / name, 0o600)
        done: list[str] = []
        try:
            for name, target in targets.items():
                target.parent.mkdir(parents=True, exist_ok=True)
                conn = claimed.get(name) or sqlite3.connect(target, isolation_level=None)
                claimed[name] = conn
                _write_into(src / name, conn)
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise SystemExit(f"{target} failed integrity_check after the restore")
                done.append(name)
        except BaseException:
            for name in done:  # put back what was already replaced, then fail
                if (keep / name).exists():
                    _write_into(keep / name, claimed[name])
            raise
        return done
    finally:
        for conn in claimed.values():
            conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("command", choices=["backup", "restore"])
    ap.add_argument("--from", dest="src", type=Path, help="backup folder to restore")
    ap.add_argument("--root", type=Path, default=ROOT)
    a = ap.parse_args(argv)
    os.umask(0o077)  # backups hold case data: owner only
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    if a.command == "backup":
        out = a.root / "var/backups" / stamp
        m = backup(a.root, out)
        print(f"backup {out}: " + ", ".join(f"{k} {v['sha256'][:12]}" for k, v in m.items()))
        return 0
    if a.src is None:
        raise SystemExit("restore needs --from var/backups/<dir> (make restore FROM=...)")
    done = restore(a.root, a.src, stamp=stamp)
    print(f"restored {', '.join(done)} from {a.src}")
    print(f"previous files: var/backups/pre-restore-{stamp}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
