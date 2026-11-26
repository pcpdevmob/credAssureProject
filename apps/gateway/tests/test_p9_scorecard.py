"""U5 (P9): the evaluator scorecard reads `make eval` runs and `make baseline` results only."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


def _run(
    root: Path, name: str, model: str, ablation: str | None, passes: dict[str, tuple[int, int]]
) -> None:
    d = root / name
    d.mkdir(parents=True)
    rows = [
        {"id": f"{c}{i}", "category": c, "passed": i < ok}
        for c, (ok, n) in passes.items()
        for i in range(n)
    ]
    (d / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (d / "summary.json").write_text(json.dumps({"meta": {"model": model, "ablation": ablation}}))


def test_U5_scorecard_newest_real_runs_and_best_baseline(
    make_client: Callable[..., Any], login: Callable[..., dict[str, str]], tmp_path: Path
) -> None:
    ev, base = tmp_path / "eval", tmp_path / "baseline"
    _run(ev, "20261118T100000", "qwen3:8b", None, {"offers": (14, 15)})
    _run(ev, "20261118T110000", "qwen3:8b", None, {"offers": (15, 15)})  # newest full wins
    _run(ev, "20261118T120000", "FakeLLM", None, {"offers": (1, 15)})  # mechanics only: ignored
    _run(ev, "20261118T130000-A1", "qwen3:8b", "A1", {"offers": (6, 15)})
    base.mkdir()
    for name, ok in (("s1_structured", 3), ("s3_decompose", 5)):
        (base / f"{name}.jsonl").write_text(
            "".join(json.dumps({"category": "offers", "passed": i < ok}) + "\n" for i in range(15))
        )
    client: TestClient = make_client(eval_dir=ev, baseline_dir=base)
    r = client.get("/v1/eval/scorecard", headers=login(client, "demo.evaluator"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["full"]["passed"] == 15 and data["full"]["run"] == "20261118T110000"
    assert data["ablations"]["A1"]["by_category"]["offers"] == [6, 15]
    assert data["baseline"]["strategy"] == "s3_decompose" and data["baseline"]["passed"] == 5
    assert (
        client.get("/v1/eval/scorecard", headers=login(client, "demo.preparer")).status_code == 403
    )


def test_U5_scorecard_is_empty_before_any_run(
    make_client: Callable[..., Any], login: Callable[..., dict[str, str]], tmp_path: Path
) -> None:
    client: TestClient = make_client(eval_dir=tmp_path / "none", baseline_dir=tmp_path / "none")
    data = client.get("/v1/eval/scorecard", headers=login(client, "demo.evaluator")).json()
    assert data == {"baseline": None, "full": None, "ablations": {}}
