"""Architecture boundaries that import-linter cannot see (ADR 0005, scope #53)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web" / "src"


def test_web_does_not_call_fetch_directly() -> None:
    """The web app talks to the gateway only through the generated API client."""
    offenders: list[str] = []
    for path in WEB.rglob("*"):
        if path.suffix not in {".ts", ".tsx"}:
            continue
        if "fetch(" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
