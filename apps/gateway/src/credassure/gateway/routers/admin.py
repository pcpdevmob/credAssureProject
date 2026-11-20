"""Evaluator-only administration (APR-03 boundary rule, audited) and evaluation runs (Phase 11)."""

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel

from credassure.core.errors import ApiErrorCode
from credassure.gateway.deps import Svc, role
from credassure.gateway.problems import ProblemError
from credassure.security.auth import Principal, Role

router = APIRouter(prefix="/v1", tags=["admin"])
Evaluator = Annotated[Principal, role(Role.EVALUATOR)]


class Config(BaseModel):
    key: Literal["boundary_rule"]
    value: Literal["hold", "director", "vp"]


@router.post("/admin/config")
def set_config(body: Config, who: Evaluator, svc: Svc) -> dict[str, Any]:
    svc.ledger.set_config(body.key, body.value, who.user_id)
    svc.supervisor.boundary_rule = body.value  # applies to the next routing in this process
    return {"key": body.key, "value": body.value}


@router.post("/eval/runs")
def start_eval(who: Evaluator) -> None:
    raise ProblemError(501, "evaluation runs arrive in Phase 11", ApiErrorCode.NOT_IMPLEMENTED)


def _by_category(rows: list[dict[str, Any]]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for r in rows:
        if r.get("passed") is None:  # infra errors are not scored
            continue
        cell = out.setdefault(str(r.get("category")), [0, 0])
        cell[0] += bool(r["passed"])
        cell[1] += 1
    return out


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


@router.get("/eval/scorecard")
def scorecard(who: Evaluator, svc: Svc) -> dict[str, Any]:
    """U5 (P9): baseline vs system vs ablations from the newest `make eval` runs and `make
    baseline` results on this machine. Read-only; runs start from the command line (make eval)."""
    runs: dict[str, dict[str, Any]] = {}
    root = svc.settings.eval_dir
    for d in sorted(root.glob("*/"), reverse=True) if root.is_dir() else []:
        try:
            meta = json.loads((d / "summary.json").read_text())["meta"]
            label = str(meta.get("ablation") or "full")
            if label in runs or meta.get("model") == "FakeLLM":
                continue  # newest real run per label; FakeLLM runs check mechanics, never score
            rows = _rows(d / "results.jsonl")
        except (OSError, ValueError, KeyError):
            continue
        runs[label] = {
            "run": d.name,
            "model": meta.get("model"),
            "passed": sum(bool(r.get("passed")) for r in rows),
            "total": len(rows),
            "by_category": _by_category(rows),
        }
    baseline = None
    bdir = svc.settings.baseline_dir
    scored = {p.stem: _rows(p) for p in sorted(bdir.glob("s[123]*.jsonl"))} if bdir.is_dir() else {}
    if scored:
        best = max(scored, key=lambda k: sum(bool(r.get("passed")) for r in scored[k]))
        rows = scored[best]
        baseline = {
            "strategy": best,
            "passed": sum(bool(r.get("passed")) for r in rows),
            "total": len(rows),
            "by_category": _by_category(rows),
        }
    return {"baseline": baseline, "full": runs.pop("full", None), "ablations": runs, "target": 92}


@router.get("/eval/runs/{run_id}")
def get_eval(run_id: str, who: Evaluator) -> None:
    raise ProblemError(501, "evaluation runs arrive in Phase 11", ApiErrorCode.NOT_IMPLEMENTED)
