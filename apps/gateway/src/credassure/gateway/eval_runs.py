"""Evaluation runs from the API (BRD §6.1 `POST /eval/runs`, evaluator only).

A run is the same program as `make eval`: `scripts/eval_harness.py` in its own process, with its
own throwaway case.db under EVAL_DIR/<run_id>/, so it never touches the cases of the running
gateway. This module only starts that process and reads what it wrote; it computes no score.
One run at a time per gateway. Arguments are fixed choices passed as a list (no shell).
"""

import json
import os
import re
import subprocess  # nosec B404 - fixed argv built from validated enums, never a shell
import sys
import threading
import time
from pathlib import Path
from typing import Any

HARNESS = Path("scripts/eval_harness.py")  # relative to the working directory, like data/ and var/
RUN_ID = re.compile(r"^\d{8}T\d{6}(?:-A[1-5])?$")
_lock = threading.Lock()
_active: dict[str, subprocess.Popen[bytes]] = {}


class HarnessMissingError(RuntimeError):
    pass


class RunActiveError(RuntimeError):
    pass


def _alive() -> str | None:
    for run_id, proc in list(_active.items()):
        if proc.poll() is None:
            return run_id
    return None


def start(eval_dir: Path, *, ablation: str | None, only: list[str] | None, fake: bool) -> str:
    """Start one harness process; returns its run id (the folder name under ``eval_dir``)."""
    if not HARNESS.is_file():
        raise HarnessMissingError(str(HARNESS))
    with _lock:
        running = _alive()
        if running is not None:
            raise RunActiveError(running)
        run_id = time.strftime("%Y%m%dT%H%M%S") + (f"-{ablation}" if ablation else "")
        argv = [sys.executable, str(HARNESS), "--out-dir", str(eval_dir), "--stamp", run_id]
        if ablation:
            argv += ["--ablation", ablation]
        if only:
            argv += ["--only", *only]
        if fake:
            argv.append("--fake")
        eval_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ | {"APP_ENV": "dev", "LOG_LEVEL": "WARNING"}  # as `make eval` sets them
        with (eval_dir / f"{run_id}.log").open("wb") as log:
            # argv is a list of fixed choices validated by the route (no shell, no user text)
            _active[run_id] = subprocess.Popen(  # noqa: S603  # nosec B603
                argv, stdout=log, stderr=subprocess.STDOUT, env=env
            )
    return run_id


def status(eval_dir: Path, run_id: str) -> dict[str, Any] | None:
    """What the run has written so far, or None for an unknown id. Never returns log text."""
    if not RUN_ID.fullmatch(run_id):
        return None
    folder = eval_dir / run_id
    proc = _active.get(run_id)
    if not folder.is_dir() and proc is None:
        return None
    results = folder / "results.jsonl"
    rows = (
        [json.loads(x) for x in results.read_text(encoding="utf-8").splitlines() if x.strip()]
        if results.is_file()
        else []
    )
    by_category: dict[str, list[int]] = {}
    for r in rows:
        if r.get("passed") is None:  # infra errors are not scored
            continue
        cell = by_category.setdefault(str(r.get("category")), [0, 0])
        cell[0] += bool(r["passed"])
        cell[1] += 1
    out: dict[str, Any] = {
        "run_id": run_id,
        "done": len(rows),
        "passed": sum(bool(r.get("passed")) for r in rows),
        "by_category": by_category,
        "meta": None,
    }
    summary = folder / "summary.json"
    if summary.is_file():
        try:
            out["meta"] = json.loads(summary.read_text(encoding="utf-8")).get("meta")
        except ValueError:
            out["meta"] = None
        return out | {"status": "finished"}
    if proc is not None and proc.poll() is None:
        return out | {"status": "running"}
    code = proc.returncode if proc is not None else None
    return out | {"status": "failed" if code else "incomplete", "exit_code": code}
