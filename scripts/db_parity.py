"""ADR 0039 parity check: the same items on SQLite and on MySQL give the same results.

    CREDASSURE_TEST_MYSQL_URL=mysql+pymysql://u:pw@127.0.0.1/ca uv run python scripts/db_parity.py

Runs the frozen test-set items (default: every category except `regulatory`, which needs the
ingested corpus) through the gateway twice with FakeLLM, once with case.db on SQLite and once on
MySQL, then compares, item by item, the verdict and the answer, and across the whole database every
ledger fact (key, version, value, unit, source), every approval and the sequence of audit events
with a verified hash chain. Ids, times and trace ids are normalised; nothing else is. FakeLLM makes
both runs deterministic, so any difference is the database's. Exit 1 on any difference.

Not a score: FakeLLM checks mechanics and storage, the model is measured by `make eval` on SQLite.
"""

import argparse
import json
import re
import secrets
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from credassure.engines.routing import route
from credassure.evaluation import harness
from credassure.gateway.main import create_app
from credassure.gateway.settings import Settings
from credassure.ledger import reads, session, testing
from credassure.ledger.seed import seed
from credassure.llm.fake import FakeLLM

ROOT = Path(__file__).resolve().parents[1]
VOLATILE = [
    (re.compile(r"\b[0-9a-f]{32}\b"), "<hex32>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "<uuid>"),
    (re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(\+00:00|Z)?"), "<ts>"),
    (re.compile(r"\b[0-9a-f]{64}\b"), "<sha256>"),
]
QUERIES = {
    "facts": "SELECT case_id, `key`, version, value_text, unit, source_type, source_ref, "
    "produced_by FROM ledger_facts ORDER BY case_id, `key`, version",
    "approvals": "SELECT case_id, role, decision, return_stage, comment FROM approvals "
    "ORDER BY case_id, id",
    "audit": "SELECT seq, case_id, event_type FROM audit_log ORDER BY seq",
    "cases": "SELECT id, status, current_stage, route FROM cases ORDER BY id",
}


def _norm(value: Any) -> Any:
    if isinstance(value, str):
        for pattern, repl in VOLATILE:
            value = pattern.sub(repl, value)
    return value


def _route(amount: Decimal, rule: str) -> str:  # the harness's routing oracle (eval_harness.py)
    return str(route(amount, rule))  # type: ignore[arg-type]


def run(target: Path | str, items: list[dict[str, Any]], tmp: Path) -> dict[str, Any]:
    password = secrets.token_urlsafe(18)
    seed(target, {"SEED_PASSWORD": password})
    overrides: dict[str, Any] = {
        "_env_file": None,
        "app_env": "test",
        "llm_enabled": True,
        "tracing_enabled": False,
        "jwt_secret": secrets.token_urlsafe(48),
        "rate_limit": "100000/minute",
        "mfa_enforced": False,
        "llm_cache_path": None,
        "case_db": tmp / "case.db",
        "checkpoint_db": tmp / "checkpoints.db",
    }
    if session.is_url(target):
        overrides["case_database_url"] = str(target)
    settings = Settings(**overrides)
    with TestClient(create_app(settings, llm=FakeLLM())) as client:
        h = harness.Harness(client, password, route_fn=_route)
        rows = h.run(items)
    engine = session.case_engine(target)
    tables: dict[str, list[list[Any]]] = {}
    with engine.connect() as c:
        quote = "`" if engine.dialect.name == "mysql" else '"'
        for name, sql in QUERIES.items():
            rows_ = c.execute(text(sql.replace("`", quote))).all()
            tables[name] = [[_norm(v) for v in r] for r in rows_]
    with session.transaction(engine) as s:
        broken = reads.verify_chain(s)
    engine.dispose()
    return {
        "items": {
            r.id: {"passed": r.passed, "answer": _norm(json.dumps(r.answer, sort_keys=True))}
            for r in rows
        },
        "tables": tables,
        "chain_broken": broken,
    }


def diff(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    out = []
    for item in sorted(set(a["items"]) | set(b["items"])):
        if a["items"].get(item) != b["items"].get(item):
            out.append(f"item {item}: sqlite={a['items'].get(item)} mysql={b['items'].get(item)}")
    for name in QUERIES:
        ra, rb = a["tables"][name], b["tables"][name]
        if ra != rb:
            first = next(
                (i for i, (x, y) in enumerate(zip(ra, rb, strict=False)) if x != y),
                min(len(ra), len(rb)),
            )
            out.append(
                f"{name}: {len(ra)} vs {len(rb)} rows; first difference at row {first}: "
                f"sqlite={ra[first] if first < len(ra) else None} "
                f"mysql={rb[first] if first < len(rb) else None}"
            )
    for label, r in (("sqlite", a), ("mysql", b)):
        if r["chain_broken"]:
            out.append(f"{label}: audit chain broken at {r['chain_broken'][:5]}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--only", nargs="*", help="categories (default: all but regulatory)")
    ap.add_argument("--out", type=Path, default=ROOT / "var" / "parity")
    args = ap.parse_args()
    url = testing.mysql_url()
    if url is None:
        sys.exit(f"set {testing.ENV} to a MySQL server URL (the user may create databases)")
    items = [
        i
        for i in harness.load()
        if (i["category"] in args.only if args.only else i["category"] != "regulatory")
    ]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "sqlite").mkdir(exist_ok=True)
    (args.out / "mysql").mkdir(exist_ok=True)
    sqlite_db = args.out / "sqlite" / "case.db"
    sqlite_db.unlink(missing_ok=True)
    a = run(sqlite_db, items, args.out / "sqlite")
    with testing.database(url, "parity") as mysql_db:
        b = run(mysql_db, items, args.out / "mysql")
    found = diff(a, b)
    report = {
        "items": len(items),
        "categories": sorted({i["category"] for i in items}),
        "passed_sqlite": sum(v["passed"] for v in a["items"].values()),
        "passed_mysql": sum(v["passed"] for v in b["items"].values()),
        "rows": {n: len(a["tables"][n]) for n in QUERIES},
        "differences": found,
    }
    (args.out / "parity.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "differences"}))
    for line in found:
        print("DIFF", line[:400])
    print("PARITY OK" if not found else f"PARITY FAILED: {len(found)} differences")
    return 0 if not found else 1


if __name__ == "__main__":
    sys.exit(main())
