"""Progress of an evaluation run (BRD §6.1 `GET /eval/runs/{id}`, evaluator only). Read-only.

A run is started from the command line (`make eval`): the gateway starts no process (ASI05,
tests/test_p8_owasp_asi.py). The harness writes EVAL_DIR/<run_id>/results.jsonl row by row and
summary.json at the end; this module reads those two files and computes no score.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUN_ID = re.compile(r"^\d{8}T\d{6}(?:-A[1-5])?$")  # the folder name `make eval` prints


def status(eval_dir: Path, run_id: str) -> dict[str, Any] | None:
    """What the run has written so far, or None for an unknown id. Never returns log text.
    ``status`` is finished (summary written) or unfinished (still running, or stopped early:
    ``updated_at`` says when it last wrote a result)."""
    if not RUN_ID.fullmatch(run_id):
        return None
    folder = eval_dir / run_id
    if not folder.is_dir():
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
    last = results if results.is_file() else folder
    out: dict[str, Any] = {
        "run_id": run_id,
        "status": "unfinished",
        "done": len(rows),
        "passed": sum(bool(r.get("passed")) for r in rows),
        "by_category": by_category,
        "updated_at": datetime.fromtimestamp(last.stat().st_mtime, UTC).isoformat(),
        "meta": None,
    }
    summary = folder / "summary.json"
    if summary.is_file():
        out["status"] = "finished"
        try:
            out["meta"] = json.loads(summary.read_text(encoding="utf-8")).get("meta")
        except ValueError:
            out["meta"] = None
    return out
