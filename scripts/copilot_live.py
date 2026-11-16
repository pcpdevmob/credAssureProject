"""E8 live run: the copilot's 44 frozen items through the API on the configured model (9e).

    make copilot-live            # MODELS=local: Ollama qwen3:8b + the ingest's embedder/Chroma

A throwaway case.db in the scratch directory given by --out-dir (default var/e8-live), seeded with a
generated password; the real model, corpus and vector store from the environment. Scored with the
frozen scorers; one JSONL row per item plus a per-category summary on stdout. Reads
data/frozen/v1 and the testset only; writes only under --out-dir.
"""

import argparse
import json
import secrets
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from credassure.evaluation.check_corpus_refs import known_doc_ids
from credassure.evaluation.scorers import score
from credassure.gateway.main import create_app
from credassure.gateway.settings import Settings
from credassure.ledger import reads
from credassure.ledger.seed import seed
from credassure.ledger.session import case_engine, transaction

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/frozen/v1"
KINDS = ("order", "opening_position", "costs", "receipts", "receivables", "payables", "inventory")
NEW_CASE = {
    "msme_name": "Live Eval Electronics Pvt Ltd",
    "order_ref": "PO-E8",
    "order_value_paise": 3_20_00_000_00,
    "indicative_amount_paise": 2_00_00_000_00,
    "due_date": "2027-05-15",
}
CATEGORIES = ("regulatory", "refusal", "injection", "isolation")


def _login(c: TestClient, user: str, password: str) -> dict[str, str]:
    r = c.post("/v1/auth/token", json={"username": user, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _post(c: TestClient, h: dict[str, str], cid: str, kind: str, path: Path) -> list[str]:
    mime = {".json": "application/json", ".csv": "text/csv", ".md": "text/markdown"}[path.suffix]
    r = c.post(
        f"/v1/cases/{cid}/files",
        params={"kind": kind},
        files={"file": (path.name, path.read_bytes(), mime)},
        headers=h,
    )
    r.raise_for_status()
    return list(r.json()["injection_flags"])


def _case(c: TestClient, h: dict[str, str], frozen: str, run: bool) -> tuple[str, list[str]]:
    cid: str = c.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    flags: list[str] = []
    for kind in KINDS:
        ext = "json" if kind in ("order", "opening_position") else "csv"
        flags += _post(c, h, cid, kind, DATA / "cases" / frozen / f"{kind}.{ext}")
    for offer in sorted((DATA / "offers" / frozen).glob("*.v1.json")):
        doc = json.loads(offer.read_text())["kfs_doc_id"]
        flags += _post(c, h, cid, "offer", offer)
        flags += _post(c, h, cid, "kfs", DATA / "kfs" / f"{doc}.md")
        flags += _post(c, h, cid, "kfs", DATA / "kfs" / f"{doc}-SCH.md")
    if run:
        for stage in ("onboarding", "working-capital", "lendwise"):
            c.post(f"/v1/agents/{stage}/cases/{cid}/run", headers=h).raise_for_status()
    return cid, flags


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "var" / "e8-live")
    ap.add_argument("--only", nargs="*", default=list(CATEGORIES), choices=CATEGORIES)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    db = args.out_dir / f"case-{time.strftime('%Y%m%dT%H%M%S')}.db"
    password = secrets.token_urlsafe(18)
    seed(db, {"SEED_PASSWORD": password})
    settings = Settings(
        case_db=db,
        jwt_secret=secrets.token_urlsafe(48),
        tenant_id="default",
        tracing_enabled=False,
        rate_limit="100000/minute",
    )
    if not settings.llm_enabled:
        sys.exit("LLM_ENABLED is false: the live run measures the model (use the test suite)")
    items = [json.loads(x) for x in (ROOT / "evaluation/testset/v1/items.jsonl").open()]
    known = known_doc_ids()
    rows: list[dict[str, Any]] = []
    with TestClient(create_app(settings)) as c:
        h = _login(c, "demo.preparer", password)
        base, _ = _case(c, h, "CA-2026-0001", run=False)
        for item in (i for i in items if i["category"] in args.only):
            t0 = time.monotonic()
            q, actor = item["input"].get("question"), item["input"]["actor"]
            if item["category"] == "injection" and not q:
                cid, flags = _case(c, h, item["input"]["case_id"], run=True)
                ranking = c.get(f"/v1/cases/{cid}/offers", headers=h).json()["ranking"]
                if item["input"].get("stage") == "negotiation_reply":
                    reply = c.post(f"/v1/agents/lendwise/cases/{cid}/negotiate", headers=h).json()
                    with transaction(case_engine(db)) as s:
                        f = reads.get_latest(s, "default", cid, "lw.negotiation.reply_flags")
                    flagged, text = f is not None and f.value_text != "none", reply["message"]
                    ranking = c.get(f"/v1/cases/{cid}/offers", headers=h).json()["ranking"]
                else:
                    res = c.get(f"/v1/agents/lendwise/cases/{cid}/result", headers=h).json()
                    flagged, text = bool(flags), res.get("narrative") or ""
                answer: dict[str, Any] = {
                    "ranking": ranking,
                    "injection_flagged": flagged,
                    "answer": text,
                }
            else:
                cid = base
                if item["category"] == "injection":
                    cid, _ = _case(c, h, item["input"]["case_id"], run=True)
                r = c.post(
                    f"/v1/cases/{cid}/chat",
                    json={"message": q},
                    headers=_login(c, actor, password),
                )
                answer = (
                    {"refused": True, "answer": r.json().get("detail", ""), "citations": []}
                    if r.status_code == 404
                    else r.json()
                )
            scored = answer | {
                "citations": sorted({x["doc_id"] for x in answer.get("citations") or []})
            }
            result = score(item, scored, known)
            rows.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "subtype": item.get("subtype"),
                    "passed": result["passed"],
                    "failure_class": result["failure_class"],
                    "detail": result["detail"],
                    "answer": answer.get("answer"),
                    "citations": answer.get("citations"),
                    "refusal_code": answer.get("refusal_code"),
                    "trace_id": answer.get("trace_id"),
                    "latency_s": round(time.monotonic() - t0, 1),
                }
            )
            print(f"{item['id']} {'PASS' if result['passed'] else 'FAIL'} {result['detail']}")
    out = args.out_dir / "results.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    total, ok = (
        Counter(r["category"] for r in rows),
        Counter(r["category"] for r in rows if r["passed"]),
    )
    for cat in CATEGORIES:
        if total[cat]:
            print(f"{cat:<11} {ok[cat]}/{total[cat]}")
    print(f"results: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
