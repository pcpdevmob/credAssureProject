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
        if path.name == "http.ts":  # same-origin auth service only (ADR 0022)
            continue
        if "fetch(" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_chroma_runs_embedded_only() -> None:
    """The accepted chromadb advisories (docs/security/risk-register.md) are all in Chroma's HTTP
    server. Keep that true: no Compose service runs a Chroma server, no code opens an HTTP client.
    """
    compose = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "deploy").rglob("*.y*ml"))
    assert "chroma" not in compose.lower()
    code = [
        str(p.relative_to(ROOT))
        for top in ("apps", "agents", "packages", "evaluation")
        for p in (ROOT / top).rglob("*.py")
        if ".venv" not in p.parts
        and any(s in p.read_text(encoding="utf-8") for s in ("HttpClient(", "AsyncHttpClient("))
    ]
    assert code == []
    # ADR 0024: no Chroma network listener either (server module or the `chroma run` CLI).
    listener = ("chromadb.server", "chromadb.app", "chroma run")
    files = [ROOT / "Makefile", *(ROOT / "scripts").rglob("*"), *(ROOT / "deploy").rglob("*")]
    files += [p for top in ("apps", "agents", "packages") for p in (ROOT / top).rglob("*.py")]
    hits = [
        str(p.relative_to(ROOT))
        for p in files
        if p.is_file()
        and ".venv" not in p.parts
        and any(s in p.read_text(encoding="utf-8", errors="ignore") for s in listener)
    ]
    assert hits == []
