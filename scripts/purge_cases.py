"""One-off, audited removal of test cases from a case.db (pending Phase 10's DELETE endpoint).

    uv run python scripts/purge_cases.py --db var/case.db CA-2026-0016 CA-2026-0017   # dry run
    uv run python scripts/purge_cases.py --db var/case.db CA-2026-0016 --yes          # really purge

ledger_facts and approvals are append-only (OBJ-08, APR-04) and have foreign keys to cases, so the
two DELETE triggers are dropped and recreated inside ONE transaction. The audit rows are never
touched; a CASES_PURGED event is appended to the hash chain, which is re-verified before commit.
"""

# ruff: noqa: S608  (table names are constants in this file; every case id is a bound parameter)
import argparse
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from credassure.ledger.reads import verify_chain
from credassure.ledger.session import case_engine, transaction
from credassure.ledger.writes import append_audit

TRIGGERS = ("ledger_facts", "approvals")
# children first (foreign keys are ON); offer_evaluations hangs off offers
CHILDREN = (
    "chat_messages",
    "negotiation_messages",
    "approvals",
    "ledger_facts",
    "stage_runs",
    "jobs",
    "case_files",
    "run_locks",
)


def _in(ids: list[str]) -> tuple[str, dict[str, str]]:
    keys = {f"c{i}": v for i, v in enumerate(ids)}
    return ", ".join(f":{k}" for k in keys), keys


def purge(s: Session, ids: list[str], *, dry_run: bool) -> dict[str, int]:
    marks, params = _in(ids)
    found = {r[0] for r in s.execute(text(f"SELECT id FROM cases WHERE id IN ({marks})"), params)}
    if missing := set(ids) - found:
        raise SystemExit(f"unknown case ids: {sorted(missing)}")
    tenant = (
        s.execute(text(f"SELECT DISTINCT tenant_id FROM cases WHERE id IN ({marks})"), params)
        .scalars()
        .all()
    )
    if len(tenant) != 1:
        raise SystemExit("cases span several tenants; purge one tenant at a time")
    threads = {f"t{i}": f"{tenant[0]}:{c}" for i, c in enumerate(ids)}
    tmarks = ", ".join(f":{k}" for k in threads)

    steps: list[tuple[str, str, dict[str, str]]] = [
        (
            "offer_evaluations",
            f"offer_row_id IN (SELECT id FROM offers WHERE case_id IN ({marks}))",
            params,
        ),
        ("offers", f"case_id IN ({marks})", params),
        *[(t, f"case_id IN ({marks})", params) for t in CHILDREN],
        ("checkpoints", f"thread_id IN ({tmarks})", threads),
        ("writes", f"thread_id IN ({tmarks})", threads),
        ("cases", f"id IN ({marks})", params),
    ]
    present = set(s.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
    steps = [st for st in steps if st[0] in present]  # checkpoint tables exist only after a run
    counts: dict[str, int] = {}
    if not dry_run:
        for t in TRIGGERS:
            s.execute(text(f"DROP TRIGGER {t}_no_delete"))
    for table, where, p in steps:
        if dry_run:
            counts[table] = s.execute(
                text(f"SELECT count(*) FROM {table} WHERE {where}"), p
            ).scalar_one()
        else:
            counts[table] = s.execute(text(f"DELETE FROM {table} WHERE {where}"), p).rowcount
    if dry_run:
        return counts
    for t in TRIGGERS:  # same SQL as migration 37bd7037b99d
        s.execute(
            text(
                f"CREATE TRIGGER {t}_no_delete BEFORE DELETE ON {t} "
                "BEGIN SELECT RAISE(ABORT, 'append-only'); END"
            )
        )
    append_audit(
        s,
        tenant_id=tenant[0],
        case_id=None,
        actor="script:purge_cases",
        event_type="CASES_PURGED",
        payload={"case_ids": sorted(ids), "rows_deleted": counts},
    )
    s.flush()
    if broken := verify_chain(s):
        raise SystemExit(f"audit chain broken at seq {broken}; rolled back")
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.epilog = "Stop the gateway first: the purge takes the write lock."
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--yes", action="store_true", help="really delete (default is a dry run)")
    ap.add_argument("ids", nargs="+", metavar="CASE_ID")
    args = ap.parse_args()
    if not args.db.exists():
        sys.exit(f"no such database: {args.db}")
    if args.yes:
        backup = args.db.with_name(f"{args.db.name}.bak-{datetime.now(UTC):%Y%m%dT%H%M%S}")
        src, dst = sqlite3.connect(args.db), sqlite3.connect(backup)
        src.backup(dst)  # online backup: a plain file copy can miss pages still in the WAL
        src.close()
        dst.close()
        print(f"backup: {backup}")
    with transaction(case_engine(args.db)) as s:
        counts = purge(s, args.ids, dry_run=not args.yes)
    print(("PURGED" if args.yes else "DRY RUN (nothing deleted)"), counts)
    print(
        "note: next_case_id is max(id)+1, so removing the newest ids lets those numbers be reused."
    )


if __name__ == "__main__":
    main()
