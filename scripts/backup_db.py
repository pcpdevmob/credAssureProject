"""Backup and restore of the SQLite stores (scope #38, NFR-06).

    make backup                          # var/backups/<UTC time>/ + MANIFEST.json
    make restore FROM=var/backups/<dir>  # stop the gateway first; keeps a pre-restore copy

Uses SQLite's online backup API, so a backup taken while the gateway runs is consistent (WAL
included). Each copy is checked with PRAGMA integrity_check and recorded with its SHA-256. A
restore checks every hash and integrity again before it replaces anything, and the current files
go to var/backups/pre-restore-<time>/ first, so a restore can itself be undone.

Backed up: case.db (cases, ledger, append-only audit), corpus.db (the ingested library) and
llm_cache.db (recorded model replies for REPLAY_MODE). Not backed up: hr.db (rebuilt from frozen
data by `make hr-db`) and Chroma (rebuilt by `make ingest`).
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORES = {"case.db": "var/case.db", "corpus.db": "var/corpus.db", "llm_cache.db": "var/llm_cache.db"}


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
    out.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, dict[str, str]] = {}
    for name, rel in STORES.items():
        src = root / rel
        if not src.exists():
            continue
        dst = out / name
        _copy(src, dst)
        if not _ok(dst):
            raise SystemExit(f"backup of {name} failed integrity_check")
        manifest[name] = {"from": rel, "sha256": _sha(dst)}
    if "case.db" not in manifest:
        raise SystemExit(f"nothing to back up: {root / STORES['case.db']} does not exist")
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def restore(root: Path, src: Path, *, stamp: str) -> list[str]:
    manifest: dict[str, dict[str, str]] = json.loads((src / "MANIFEST.json").read_text())
    for name, meta in manifest.items():  # verify everything before touching anything
        if name not in STORES or meta.get("from") != STORES[name]:
            raise SystemExit(f"unexpected entry {name!r} in {src / 'MANIFEST.json'}")
        f = src / name
        if not f.exists() or _sha(f) != meta["sha256"] or not _ok(f):
            raise SystemExit(f"{f} is missing, changed or corrupt; nothing restored")
    keep = root / "var/backups" / f"pre-restore-{stamp}"
    restored = []
    for name, meta in manifest.items():
        target = root / meta["from"]
        if target.exists():
            keep.mkdir(parents=True, exist_ok=True)
            _copy(target, keep / name)
        for side in (Path(f"{target}-wal"), Path(f"{target}-shm")):
            side.unlink(missing_ok=True)  # a stale WAL would replay over the restored file
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy(src / name, target)
        restored.append(name)
    return restored


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("command", choices=["backup", "restore"])
    ap.add_argument("--from", dest="src", type=Path, help="backup folder to restore")
    ap.add_argument("--root", type=Path, default=ROOT)
    a = ap.parse_args(argv)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    if a.command == "backup":
        out = a.root / "var/backups" / stamp
        m = backup(a.root, out)
        print(f"backup {out}: " + ", ".join(f"{k} {v['sha256'][:12]}" for k, v in m.items()))
        return 0
    if a.src is None:
        raise SystemExit("restore needs --from var/backups/<dir> (make restore FROM=...)")
    done = restore(a.root, a.src, stamp=stamp)
    print(f"restored {', '.join(done)} from {a.src}; previous files in var/backups/pre-restore-{stamp}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
