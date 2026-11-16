"""make demo-reset: rebuild the demo cases in CASE_DB (tenant "demo") by driving the real API.

    TENANT_ID=demo uv run --env-file .env python scripts/demo_reset.py

1. Refuses the e2e database, a TENANT_ID other than "demo", and a running gateway on :8000.
2. First run on a database whose users are not in tenant "demo": purge every case (audited),
   online backup, then migrate a fresh database and seed the users in tenant "demo".
   Later runs: back up, then purge only the demo tenant's cases (audited, chain re-verified).
3. Through the API (the real app in-process, same routers, auth and job runner), one demo case per
   row of DEMO_CASES (a mix of outcomes: Director, VP, held at the boundary, lender gate blocked,
   paused for data); 10 cases. None is approved. Each lists which frozen case it copies.
Case ids are max(id)+1, so after the purge every run gives the same ids and states (idempotent).
Reads data/frozen/v1 only; never writes anything outside CASE_DB and its backups.
"""

# ponytail: minimal Phase 12 pull-forward; replay cache and the blocked/approved cases come later.
import importlib.util
import json
import os
import socket
import sqlite3
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import text

from credassure.gateway.main import create_app
from credassure.gateway.settings import Settings, get_settings
from credassure.ledger import migrate
from credassure.ledger.seed import seed
from credassure.ledger.session import case_engine, transaction

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FROZEN = ROOT / "data" / "frozen" / "v1"
E2E_DB = ROOT / "var" / "case-e2e.db"
TENANT = "demo"
KINDS = ("order", "opening_position", "costs", "receipts", "receivables", "payables", "inventory")
# (frozen case, MSME name, upload offers, expected status, expected route, why it is in the mix)
DEMO_CASES: tuple[tuple[str, str, bool, str, str | None, str], ...] = (
    (
        "CA-2026-0001",
        "Demo Electronics Pvt Ltd",
        True,
        "AWAITING_APPROVAL",
        "director_finance",
        "2 of 3 offers eligible; the unaffordable lender is dropped",
    ),
    (
        "CA-2026-0003",
        "Demo Circuits Pvt Ltd",
        True,
        "AWAITING_APPROVAL",
        "director_finance",
        "all 3 offers eligible (floating-rate flag, hidden charge caught)",
    ),
    (
        "CA-2026-0006",
        "Demo Assemblies Pvt Ltd",
        True,
        "AWAITING_APPROVAL",
        "vp_finance",
        "need above 1.5 crore, routed to the VP",
    ),
    (
        "CA-2026-0010",
        "Demo Boundary Pvt Ltd",
        True,
        "HELD",
        "HELD",
        "need exactly 1.5 crore, held by the boundary rule",
    ),
    (
        "CA-2026-0007",
        "Demo Sensors Pvt Ltd",
        True,
        "AWAITING_APPROVAL",
        "vp_finance",
        "VP route, all 3 offers eligible, a confirmed mitigation",
    ),
    (
        "CA-2026-0008",
        "Demo Mid-Size Pvt Ltd",
        True,
        "AWAITING_APPROVAL",
        "vp_finance",
        "medium enterprise: CGTMSE offer flagged ineligible",
    ),
    (
        "CA-2026-0004",
        "Demo Fees Pvt Ltd",
        True,
        "PAUSED",
        None,
        "only 1 eligible offer: lender gate blocks",
    ),
    (
        "CA-2026-0005",
        "Demo Rejects Pvt Ltd",
        True,
        "PAUSED",
        None,
        "no eligible offer: missing term, mismatch, unaffordable",
    ),
    (
        "CA-2026-0013",
        "Demo Paused Case Pvt Ltd",
        False,
        "PAUSED",
        None,
        "no min_cash_buffer: one question to the preparer",
    ),
    (
        "CA-2026-0014",
        "Demo Conflict Pvt Ltd",
        False,
        "PAUSED",
        None,
        "conflicting receipts and a duplicate invoice id",
    ),
)
POLL_S = 15 * 60  # a live 8B model takes minutes for LendWise


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load scripts/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


purge_cases = _load("purge_cases")
e2e_guard = _load("e2e_guard")


def _backup(db: Path) -> Path:
    out = db.with_name(f"{db.name}.bak-{datetime.now(UTC):%Y%m%dT%H%M%S%f}")
    src, dst = sqlite3.connect(db), sqlite3.connect(out)
    src.backup(dst)  # online backup: includes pages still in the WAL
    src.close()
    dst.close()
    return out


def _passwords(settings: Settings) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k.startswith("SEED_PASSWORD_")}
    if settings.seed_password is not None:
        env["SEED_PASSWORD"] = settings.seed_password.get_secret_value()
    return env


def reset_db(settings: Settings) -> None:
    db = settings.case_db
    if db.exists():
        engine = case_engine(db)
        with transaction(engine) as s:
            tenants = set(s.execute(text("SELECT DISTINCT tenant_id FROM users")).scalars())
            cases = s.execute(text("SELECT id, tenant_id FROM cases")).all()
        if tenants and tenants != {TENANT}:  # first run: switch the database to tenant demo
            for tenant in sorted({t for _, t in cases}):
                with transaction(engine) as s:
                    purge_cases.purge(s, [c for c, t in cases if t == tenant], dry_run=False)
            engine.dispose()
            print(f"backup (pre-demo database): {_backup(db)}")
            for suffix in ("", "-wal", "-shm"):
                Path(f"{db}{suffix}").unlink(missing_ok=True)
        elif demo := [c for c, t in cases if t == TENANT]:
            print(f"backup: {_backup(db)}")
            with transaction(engine) as s:
                purge_cases.purge(s, demo, dry_run=False)
        engine.dispose()
    migrate.upgrade("case", db)
    seed(db, _passwords(settings), tenant_id=TENANT)  # idempotent: existing users are kept


def _login(client: TestClient, settings: Settings, username: str) -> dict[str, str]:
    env = _passwords(settings)
    key = "SEED_PASSWORD_" + username.replace(".", "_").upper()
    password = env.get(key) or env.get("SEED_PASSWORD")
    if not password:
        raise SystemExit(f"no password for {username}: set SEED_PASSWORD or {key}")
    r = client.post("/v1/auth/token", json={"username": username, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _upload(client: TestClient, h: dict[str, str], cid: str, kind: str, path: Path) -> None:
    mime = {".json": "application/json", ".csv": "text/csv", ".md": "text/markdown"}[path.suffix]
    r = client.post(
        f"/v1/cases/{cid}/files",
        params={"kind": kind},
        files={"file": (path.name, path.read_bytes(), mime)},
        headers=h,
    )
    if r.status_code != 201:
        raise SystemExit(f"upload {kind} {path.name}: {r.status_code} {r.text}")


def _case(client: TestClient, h: dict[str, str], frozen: str, name: str, offers: bool) -> str:
    order_value = int(
        json.loads((FROZEN / "cases" / frozen / "order.json").read_text())["order_value"]
    )
    r = client.post(
        "/v1/cases",
        json={
            "msme_name": name,
            "order_ref": f"PO-{frozen}",
            "order_value_paise": order_value * 100,
            "indicative_amount_paise": 2_00_00_000_00,
            "due_date": "2027-05-15",
        },
        headers=h,
    )
    r.raise_for_status()
    cid: str = r.json()["case_id"]
    for kind in KINDS:
        ext = "json" if kind in ("order", "opening_position") else "csv"
        _upload(client, h, cid, kind, FROZEN / "cases" / frozen / f"{kind}.{ext}")
    if offers:
        for offer in sorted((FROZEN / "offers" / frozen).glob("*.v1.json")):
            doc = json.loads(offer.read_text())["kfs_doc_id"]
            _upload(client, h, cid, "offer", offer)
            _upload(client, h, cid, "kfs", FROZEN / "kfs" / f"{doc}.md")
            _upload(client, h, cid, "kfs", FROZEN / "kfs" / f"{doc}-SCH.md")
    run = client.post(f"/v1/cases/{cid}/run", headers=h)
    if run.status_code != 202:
        raise SystemExit(f"run {cid}: {run.status_code} {run.text}")
    deadline = time.monotonic() + POLL_S
    while (job := client.get(run.json()["status_url"], headers=h).json())["status"] not in (
        "succeeded",
        "failed",
        "abandoned",
    ):
        if time.monotonic() > deadline:
            raise SystemExit(f"run {cid}: still {job['status']} after {POLL_S} s")
        time.sleep(2)
    return cid


def drive(settings: Settings) -> dict[str, dict[str, Any]]:
    views: dict[str, dict[str, Any]] = {}
    # the script is the only caller of its in-process app: lift the per-user NFR-04 limit for it
    app = create_app(settings.model_copy(update={"rate_limit": "100000/minute"}))
    with TestClient(app) as client:
        h = _login(client, settings, "demo.preparer")
        for frozen, name, offers, status, route, why in DEMO_CASES:
            cid = _case(client, h, frozen, name, offers)
            v = client.get(f"/v1/cases/{cid}", headers=h).json()
            if (v["status"], v["route"]) != (status, route):
                raise SystemExit(f"{cid} ({frozen}): expected {status}/{route} ({why}), got {v}")
            views[cid] = v
    return views


def main(settings: Settings | None = None, *, check_port: bool = True) -> dict[str, dict[str, Any]]:
    settings = settings or get_settings()
    if e2e_guard.same_file(settings.case_db, E2E_DB):
        raise SystemExit(f"refusing: CASE_DB is the e2e database ({E2E_DB}); use var/case.db")
    if settings.tenant_id != TENANT:
        raise SystemExit(f"refusing: TENANT_ID is {settings.tenant_id!r}; run with TENANT_ID=demo")
    if check_port:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", 8000)) == 0:
                raise SystemExit("refusing: something is listening on :8000; stop make run-api")
    reset_db(settings)
    views = drive(settings)
    for cid, v in views.items():
        print(f"{cid}  {v['status']:<18} route={v['route']}  question={v['question']!r}")
    return views


if __name__ == "__main__":
    main()
