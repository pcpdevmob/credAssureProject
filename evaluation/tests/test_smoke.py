"""Smoke test. Must not import the engines (independent gold)."""

import ast
from pathlib import Path

import pytest

import credassure.evaluation


def test_smoke_import() -> None:
    assert credassure.evaluation is not None


def test_evaluation_does_not_import_engines() -> None:
    root = Path(__file__).resolve().parents[1] / "src"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            assert not any(name.startswith("credassure.engines") for name in names)


def test_baseline_uses_the_product_thinking_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    from credassure.evaluation.baseline.client import thinking_off

    monkeypatch.setenv("LLM_THINKING_SWITCH", "reasoning_effort")
    assert thinking_off() == {"reasoning_effort": "none"}
    monkeypatch.delenv("LLM_THINKING_SWITCH")
    assert thinking_off() == {"chat_template_kwargs": {"enable_thinking": False}}
