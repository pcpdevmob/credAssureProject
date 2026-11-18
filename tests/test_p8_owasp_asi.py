"""Plan v3.4 P8.2 (scope #66): controls from the OWASP LLM (2026) / ASI (2026) mapping that had no
test yet. Every row of docs/security/owasp-asi-mapping.md names at least one test; these fill the
gaps for ASI05, LLM08 and LLM04/ASI04. The mapping itself is checked by test_owasp_asi_mapping.py.
"""

import ast
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = [ROOT / "agents", ROOT / "packages", ROOT / "apps" / "gateway" / "src"]
_BANNED_CALLS = {"eval", "exec", "compile", "__import__"}
_BANNED_MODULES = {"subprocess", "pickle", "marshal", "shelve", "pty"}
_BANNED_ATTRS = {
    ("os", "system"),
    ("os", "popen"),
    ("os", "execv"),
    ("os", "execve"),
    ("os", "spawnv"),
}


# Reviewed exceptions: a dev-only CLI with a fixed argv, never reachable from a request or a model.
_ALLOWED = {"packages/core/src/credassure/core/prompts.py:16 import subprocess"}


def _runtime_sources() -> list[Path]:
    out = []
    for root in SOURCE_ROOTS:
        for p in root.rglob("*.py"):
            parts = set(p.parts)
            if parts & {"tests", ".venv", "node_modules", "migrations"}:
                continue
            out.append(p)
    return out


def test_ASI05_no_runtime_module_can_execute_code_or_spawn_a_process() -> None:
    """ASI05 unexpected code execution: no eval/exec/compile, no subprocess, pickle or os.system
    anywhere an agent, package or the gateway runs. Model output therefore can never be executed."""
    sources = _runtime_sources()
    assert len(sources) > 50
    hits: list[str] = []
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in _BANNED_CALLS:
                    hits.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.func.id}()")
            elif isinstance(node, ast.Import | ast.ImportFrom):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for n in names:
                    if n.split(".")[0] in _BANNED_MODULES:
                        hits.append(f"{path.relative_to(ROOT)}:{node.lineno} import {n}")
            elif (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and (node.value.id, node.attr) in _BANNED_ATTRS
            ):
                hits.append(f"{path.relative_to(ROOT)}:{node.lineno} {node.value.id}.{node.attr}")
    assert [h for h in hits if h not in _ALLOWED] == []


_SECRET = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|api[_-]?key\s*[:=]|password\s*[:=]|secret\s*[:=]|bearer\s+[A-Za-z0-9._-]{20,}"
    r"|https?://[^\s/]+:[^\s/]+@|JWT_SECRET|LLM_API_KEY|LANGFUSE_SECRET)",
    re.IGNORECASE,
)


def test_LLM08_prompts_hold_no_secrets_or_credentials() -> None:
    """LLM08 hidden-context exposure (2026 numbering; LLM07 in 2025): a leaked system prompt
    reveals nothing, because no prompt holds a key, password, credentialed URL or secret name."""
    prompts = sorted(ROOT.glob("agents/*/src/credassure/agents/*/prompts/*.yaml"))
    assert len(prompts) >= 10
    leaks = [
        f"{p.relative_to(ROOT)}: {m.group(0)}"
        for p in prompts
        for m in _SECRET.finditer(p.read_text())
    ]
    assert leaks == []


def test_LLM04_ASI04_dependencies_and_prompts_are_locked() -> None:
    """LLM04 / ASI04 supply chain: Python and JS lock files are committed, CI installs only from the
    lock, pip-audit runs, and the agent toolset is a static registry (no dynamic tools or MCP)."""
    assert (ROOT / "uv.lock").is_file() and (ROOT / "pnpm-lock.yaml").is_file()
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "uv sync --locked" in ci
    assert "pip-audit" in (ROOT / "Makefile").read_text()
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert "workspace" in deps["tool"]["uv"]
    runtime = "\n".join(p.read_text(encoding="utf-8") for p in _runtime_sources())
    assert "import mcp" not in runtime and "from mcp" not in runtime
