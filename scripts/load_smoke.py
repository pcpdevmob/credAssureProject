"""Scope #35 performance smoke (P7.4, ARCHITECTURE Q6): N concurrent demo cases through the API.

    make load-smoke                       # 10 cases on the configured model (MODELS=local|course)
    make load-smoke ARGS="--fake"         # concurrency and locking only (FakeLLM)

Each case: create, upload the demo files, then run the onboarding, working-capital and LendWise
stages one by one through their API endpoints, timing each call client-side. Prints p50/p95 per
stage and per case, and fails if any case's outcome differs from the gold (gates, ₹1,42,00,000,
ranking) or any stage call errors. Throwaway database under var/load-smoke/; nothing else written.
Target (Q6): funding stage p95 < 60 s on the shared endpoint.
"""

import argparse
import json
import secrets
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data/frozen/v1"
KINDS = ("order", "opening_position", "costs", "receipts", "receivables", "payables", "inventory")
STAGES = ("onboarding", "working-capital", "lendwise")
Q6_P95_S = 60.0


def _p(values: list[float], q: float) -> float:
    s = sorted(values)
    return round(s[min(len(s) - 1, int(len(s) * q))], 2) if s else 0.0


def one_case(c: TestClient, h: dict[str, str]) -> dict[str, Any]:
    t0 = time.monotonic()
    cid = c.post(
        "/v1/cases",
        json={
            "msme_name": "Load Smoke Pvt Ltd",
            "order_ref": "PO-LOAD",
            "order_value_paise": 3_20_00_000_00,
            "indicative_amount_paise": 2_00_00_000_00,
            "due_date": "2027-05-15",
        },
        headers=h,
    ).json()["case_id"]
    files = [
        (
            k,
            DEMO
            / "cases/CA-2026-0001"
            / (f"{k}.json" if k in ("order", "opening_position") else f"{k}.csv"),
        )
        for k in KINDS
    ]
    for offer in sorted((DEMO / "offers/CA-2026-0001").glob("*.v1.json")):
        doc = json.loads(offer.read_text())["kfs_doc_id"]
        files += [
            ("offer", offer),
            ("kfs", DEMO / "kfs" / f"{doc}.md"),
            ("kfs", DEMO / "kfs" / f"{doc}-SCH.md"),
        ]
    for kind, path in files:
        mime = {".json": "application/json", ".csv": "text/csv", ".md": "text/markdown"}[
            path.suffix
        ]
        r = c.post(
            f"/v1/cases/{cid}/files",
            params={"kind": kind},
            files={"file": (path.name, path.read_bytes(), mime)},
            headers=h,
        )
        r.raise_for_status()
    timings: dict[str, float] = {}
    errors: list[str] = []
    for stage in STAGES:
        s0 = time.monotonic()
        r = c.post(f"/v1/agents/{stage}/cases/{cid}/run", headers=h)
        timings[stage] = time.monotonic() - s0
        if r.status_code != 202:
            errors.append(f"{stage}: {r.status_code}")
    funding = c.get(f"/v1/cases/{cid}/funding", headers=h).json()
    offers = c.get(f"/v1/cases/{cid}/offers", headers=h).json()
    ok = (
        not errors
        and (funding.get("recommended_amount") or {}).get("paise") == 1_42_00_000_00
        and offers.get("gate") == "GO"
        and offers.get("ranking") == ["OF-01-B", "OF-01-A"]
    )
    return {
        "case_id": cid,
        "ok": ok,
        "errors": errors,
        "stages": timings,
        "total": time.monotonic() - t0,
    }


def smoke(c: TestClient, password: str, n: int) -> dict[str, Any]:
    r = c.post("/v1/auth/token", json={"username": "demo.preparer", "password": password})
    r.raise_for_status()
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    with ThreadPoolExecutor(max_workers=n) as pool:
        runs = list(pool.map(lambda _: one_case(c, h), range(n)))
    per: dict[str, list[float]] = defaultdict(list)
    for run in runs:
        for stage, secs in run["stages"].items():
            per[stage].append(secs)
    totals = [run["total"] for run in runs]
    return {
        "cases": n,
        "ok": sum(run["ok"] for run in runs),
        "errors": [e for run in runs for e in run["errors"]],
        "stage_p50_s": {s: _p(v, 0.5) for s, v in per.items()},
        "stage_p95_s": {s: _p(v, 0.95) for s, v in per.items()},
        "case_p50_s": _p(totals, 0.5),
        "case_p95_s": _p(totals, 0.95),
        "case_mean_s": round(statistics.fmean(totals), 2) if totals else 0.0,
    }


def main() -> int:
    from credassure.gateway.main import create_app
    from credassure.gateway.settings import Settings
    from credassure.ledger.seed import seed

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", type=int, default=10)
    ap.add_argument("--fake", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "var" / "load-smoke")
    args = ap.parse_args()
    out = args.out_dir / time.strftime("%Y%m%dT%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    password = secrets.token_urlsafe(18)
    seed(out / "case.db", {"SEED_PASSWORD": password})
    kw: dict[str, Any] = {
        "case_db": out / "case.db",
        "jwt_secret": secrets.token_urlsafe(48),
        "tenant_id": "default",
        "rate_limit": "100000/minute",
    }
    if args.fake:
        from credassure.llm.fake import FakeLLM

        kw |= {"_env_file": None, "app_env": "test", "llm_enabled": True, "tracing_enabled": False}
        app = create_app(Settings(**kw), llm=FakeLLM())
    else:
        app = create_app(Settings(**kw))
    with TestClient(app) as c:
        result = smoke(c, password, args.cases) | {
            "model": "FakeLLM" if args.fake else "configured"
        }
    (out / "load-smoke.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    q6 = result["stage_p95_s"].get("working-capital", 0) < Q6_P95_S
    print(
        f"LOAD_SMOKE {result['ok']}/{result['cases']} ok · "
        f"Q6 funding p95 < {Q6_P95_S}s: {'PASS' if q6 else 'FAIL'}"
    )
    return 0 if result["ok"] == result["cases"] and q6 else 1


if __name__ == "__main__":
    sys.exit(main())
