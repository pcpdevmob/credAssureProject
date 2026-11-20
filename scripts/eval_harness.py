"""`make eval`: the 100 frozen items through the API on the configured model (Phase 11, P7.1).

    make eval                          # full system, MODELS=local (Ollama) or course
    make eval ARGS="--ablation A1"     # one ablation, its affected categories only (ablations.yaml)
    make eval ARGS="--fake --only routing onboarding"   # mechanics check with FakeLLM (no model)

A throwaway case.db under var/eval/<timestamp>[-<ablation>]/ seeded with a generated password; the
real model, corpus and vector store come from the environment. Writes results.jsonl, summary.json
and the reproducibility record (model, prompt versions, ablation, corpus hash). Nothing else is
written; var/case.db and the demo data are never touched.
"""

import argparse
import hashlib
import os
import secrets
import sys
import threading
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from fastapi.testclient import TestClient

from credassure.core.ports import LLMPort
from credassure.core.prompts import registry
from credassure.engines.routing import route
from credassure.evaluation import harness
from credassure.evaluation.record import data_hashes
from credassure.gateway.main import _default_llm, create_app
from credassure.gateway.settings import Settings
from credassure.ledger.seed import seed

ROOT = Path(__file__).resolve().parents[1]
ABLATIONS = ROOT / "evaluation" / "ablations" / "ablations.yaml"


class Metered:
    """LLMPort wrapper: counts calls and estimates tokens as (prompt + reply) chars / 4."""

    def __init__(self, inner: LLMPort) -> None:
        self.inner, self.calls, self.tokens = inner, 0, 0
        self._lock = threading.Lock()

    def complete(self, prompt: str, *, name: str = "default", json_schema: Any = None) -> str:
        out = self.inner.complete(prompt, name=name, json_schema=json_schema)
        with self._lock:
            self.calls += 1
            self.tokens += (len(prompt) + len(out)) // 4
        return out

    def __getattr__(self, item: str) -> Any:  # breaker state and the rest pass through
        return getattr(self.inner, item)

    def reading(self) -> tuple[int, int]:
        with self._lock:
            return self.calls, self.tokens


def _route(amount: Decimal, rule: str) -> str:
    return str(route(amount, rule))  # type: ignore[arg-type]


def _corpus_hash() -> str:
    lock = ROOT / "data" / "corpus" / "manifest.lock.json"
    return hashlib.sha256(lock.read_bytes()).hexdigest()[:16] if lock.exists() else "none"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "var" / "eval")
    ap.add_argument("--ablation", choices=["A1", "A2", "A3", "A4", "A5"], default=None)
    ap.add_argument(
        "--only", nargs="*", default=None, help="categories (default: all, or the ablation's)"
    )
    ap.add_argument("--ids", nargs="*", default=None, help="item ids")
    ap.add_argument("--fake", action="store_true", help="FakeLLM: mechanics only, not a score")
    ap.add_argument(
        "--use-cache",
        action="store_true",
        help="reuse cached model replies (debugging only; a scored run always calls the model)",
    )
    args = ap.parse_args()

    stamp = time.strftime("%Y%m%dT%H%M%S") + (f"-{args.ablation}" if args.ablation else "")
    out = args.out_dir / stamp
    out.mkdir(parents=True, exist_ok=True)
    db = out / "case.db"
    password = secrets.token_urlsafe(18)  # throwaway accounts; never printed
    seed(db, {"SEED_PASSWORD": password})
    overrides: dict[str, Any] = {
        "case_db": db,
        "jwt_secret": secrets.token_urlsafe(48),
        "tenant_id": "default",
        "rate_limit": "100000/minute",
        "ablation": args.ablation,
        "mfa_enforced": False,  # ADR 0038: the frozen evaluation signs in with a password only
    }
    # A scored run measures the model, never the response cache: the cache key has no server
    # context length, so replies cached under another context would be replayed (G4 live run).
    if not args.use_cache:
        overrides["llm_cache_path"] = None
    if args.fake:
        overrides |= {
            "_env_file": None,
            "app_env": "test",
            "llm_enabled": True,
            "tracing_enabled": False,
        }
    settings = Settings(**overrides)
    if settings.app_env == "demo":
        sys.exit("APP_ENV=demo: evaluation runs on the non-demo path")
    if args.fake:
        from credassure.llm.fake import FakeLLM

        inner: LLMPort | None = FakeLLM()
    else:
        inner = _default_llm(settings)
        if inner is None:
            sys.exit(
                "LLM_ENABLED is false: the evaluation measures the model (use --fake for mechanics)"
            )
    assert inner is not None  # noqa: S101 - narrowed above
    llm = Metered(inner)

    items = harness.load()
    cats = args.only
    if args.ablation and not cats:
        cats = yaml.safe_load(ABLATIONS.read_text())[args.ablation]["categories"]
    items = [
        i
        for i in items
        if (not cats or i["category"] in cats) and (not args.ids or i["id"] in args.ids)
    ]

    meta = {
        "model": "FakeLLM" if args.fake else settings.llm_model,
        "endpoint": "fake" if args.fake else settings.llm_base_url,
        "ablation": args.ablation,
        "categories": cats or "all",
        "items": len(items),
        "prompt_versions": {n: p.version for n, p in registry().items()},
        "corpus_lock": _corpus_hash(),
        "data_hashes": data_hashes(),  # v1 + v2 lender scripts (ADR 0037)
        "lender_scripts_dir": str(settings.lender_scripts_dir),
        "reranker": settings.reranker,
        "llm_cache": bool(settings.llm_cache_path),
        "price_per_1k": float(os.environ.get("EVAL_PRICE_PER_1K", "0") or 0),
        "started": stamp,
    }
    with TestClient(create_app(settings, llm=llm)) as client:
        h = harness.Harness(
            client, password, route_fn=_route, meter=llm.reading, price_per_1k=meta["price_per_1k"]
        )

        def show(r: harness.Row) -> None:
            print(
                f"{r.id} {r.category:<11} {'PASS' if r.passed else 'FAIL'} "
                f"{r.brd_class or ''} {r.detail[:90]}",
                flush=True,
            )

        rows = h.run(items, on_row=show)
    s = harness.write(rows, out, meta)
    print(f"EVAL {s['passed']}/{s['total']}  {s['by_category']}  taxonomy={s['taxonomy']}")
    print(f"results: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
