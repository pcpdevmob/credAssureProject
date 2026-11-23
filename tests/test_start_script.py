"""`make start` / scripts/start.sh: one command that brings up the local stack (model, Langfuse if
set up, API, web). Checked statically here; it was run end to end with the model and tracing off
(start, Ctrl-C, make stop, an API that cannot start) when it was written."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/start.sh"


def test_start_script_is_valid_bash_and_executable() -> None:
    assert SCRIPT.stat().st_mode & 0o100
    subprocess.run(["/bin/bash", "-n", str(SCRIPT)], check=True)  # noqa: S603


def test_start_script_never_reads_the_env_file() -> None:
    """Only `[ -f .env ]`: the gateway reads .env itself through make run-api."""
    text = SCRIPT.read_text(encoding="utf-8")
    reader = r"\b(cat|source|grep|sed|awk|head|tail|less|more|cut|read)\b[^\n]*\s\.env\b"
    reads = re.findall(reader, text) + re.findall(
        r"(^|[;&|]\s*)\.\s+\.env\b|<\s*\.env\b", text, re.M
    )
    assert reads == []
    assert "[ -f .env ]" in text


def test_make_start_and_stop_call_the_script() -> None:
    make = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "\tMODELS=$(MODELS) bash scripts/start.sh $(ARGS)\n" in make
    assert "\tbash scripts/start.sh stop\n" in make


def test_help_lists_every_option() -> None:
    out = subprocess.run(  # noqa: S603
        ["/bin/bash", str(SCRIPT), "--help"], capture_output=True, text=True, check=True
    ).stdout
    for option in ("--reset", "--no-model", "--no-langfuse", "make stop", "MODELS=course"):
        assert option in out, option
