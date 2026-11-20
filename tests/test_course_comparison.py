"""Course-endpoint comparison tools: run diff and embedding parity (ADR 0036 follow-up)."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS = Path(__file__).parent.parent / "scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run(folder: Path, model: str, rows: list[tuple[str, str, bool]]) -> Path:
    folder.mkdir()
    lines = [
        json.dumps({"id": i, "category": c, "passed": p, "latency_s": 2.0, "tokens": 10})
        for i, c, p in rows
    ]
    (folder / "results.jsonl").write_text("\n".join(lines) + "\n")
    (folder / "summary.json").write_text(json.dumps({"meta": {"model": model, "llm_cache": False}}))
    return folder


def test_compare_runs_counts_shared_items_and_lists_flips(tmp_path: Path) -> None:
    cr = _load("compare_runs")
    a = _run(
        tmp_path / "a",
        "qwen3:8b",
        [("T001", "regulatory", True), ("T002", "regulatory", False), ("T026", "onboarding", True)],
    )
    b = _run(
        tmp_path / "b",
        "Qwen/Qwen3-8B",
        [("T001", "regulatory", False), ("T002", "regulatory", True), ("T050", "cashflow", True)],
    )
    text, flips = cr.report(a, b)
    assert flips == 2  # T026 and T050 are not in both runs, so they are not compared
    assert "| regulatory | 2 | 1 | 1 | +0 |" in text
    assert "| T001 | regulatory | PASS | FAIL |" in text and "T026" not in text
    assert "`qwen3:8b`" in text and "`Qwen/Qwen3-8B`" in text


def test_embed_parity_cosine() -> None:
    ep = _load("embed_parity")
    assert ep.cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert abs(ep.cosine([1.0, 0.0], [0.0, 1.0])) < 1e-12
    assert ep.cosine([0.0, 0.0], [1.0, 0.0]) == 0.0
