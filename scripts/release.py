"""Release bundle (scope #37): what exactly v<version> is, in one folder.

    make release VERSION=1.0.0      # var/release/v1.0.0/ (gitignored); attach to the release

RELEASE.json records the git commit, the frozen-data and test-set hashes, the guardrail policy
lock, the newest evaluation reports, the CHANGELOG section and, where Docker has built them, the
image IDs and base-image digests. sbom.cdx.json is the CycloneDX SBOM (scripts/sbom.py). Nothing
here calls the network; missing pieces are recorded as missing, never invented.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess  # nosec B404 - fixed argv, no shell
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sbom

ROOT = Path(__file__).resolve().parents[1]
HASHED = (
    "data/frozen/v1/SHA256SUMS",
    "data/frozen/v2/SHA256SUMS",  # v2 lender scripts, ADR 0037
    "evaluation/FROZEN.sha256",
    "evaluation/safety_v2/FROZEN.sha256",  # recorded once the suite is frozen (ADR 0031)
    "config/guardrails.lock",
    "uv.lock",
    "package-lock.json",
    "openapi.json",
)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(*argv: str) -> str | None:
    try:
        return subprocess.run(  # noqa: S603  # nosec B603 - fixed argv from this file
            list(argv), cwd=ROOT, check=True, capture_output=True, text=True, timeout=60
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def changelog_section(text: str, version: str) -> str | None:
    m = re.search(rf"^## \[{re.escape(version)}\].*?(?=^## \[|\Z)", text, re.M | re.S)
    return m.group(0).strip() if m else None


def newest_reports(root: Path) -> dict[str, str]:
    """Newest report per evaluation id (E4, E10, E13, ...), by the date in the file name
    (E10-2026-11-17b.md is after E10-2026-11-17.md; E10-routes-2026-11-07.md is older)."""
    dated = []
    for p in (root / "evaluation/reports").glob("E*-*.md"):
        m = re.search(r"(\d{4}-\d{2}-\d{2})(\w*)\.md$", p.name)
        if m:
            dated.append((m.group(1), m.group(2), p))
    out: dict[str, Path] = {}
    for _, _, p in sorted(dated):
        out[p.name.split("-", 1)[0]] = p  # later dates overwrite earlier ones
    return {k: str(v.relative_to(root)) for k, v in sorted(out.items())}


def images() -> dict[str, str] | str:
    names = _run("docker", "compose", "-f", "deploy/compose/compose.yaml", "config", "--images")
    if names is None:
        return "docker not available on this machine: build the images and rerun"
    if not names.split():
        return "no images listed by docker compose on this machine"
    found = {}
    for name in names.split():
        ref = _run("docker", "image", "inspect", name, "--format", "{{.Id}}")
        found[name] = ref or "not built"
    return found


def bundle(root: Path, version: str, out: Path) -> dict[str, Any]:
    if not SEMVER.match(version):
        raise SystemExit(f"VERSION must be semver like 1.0.0, got {version!r}")
    section = changelog_section((root / "CHANGELOG.md").read_text(encoding="utf-8"), version)
    if section is None:
        raise SystemExit(f"CHANGELOG.md has no '## [{version}]' section; add it first")
    out.mkdir(parents=True, exist_ok=True)
    reports = newest_reports(root)
    record = {
        "version": version,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": _run("git", "rev-parse", "HEAD"),
        "git_dirty": bool(_run("git", "status", "--porcelain")),
        "hashes": {p: _sha(root / p) for p in HASHED if (root / p).exists()},
        "evaluation_reports": reports,
        "images": images(),
        "changelog": section,
    }
    (out / "RELEASE.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    (out / "sbom.cdx.json").write_text(json.dumps(sbom.sbom(root, version), indent=2) + "\n")
    (out / "reports").mkdir(exist_ok=True)
    for rel in reports.values():
        shutil.copy2(root / rel, out / "reports" / Path(rel).name)
    return record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True)
    a = ap.parse_args(argv)
    out = ROOT / "var/release" / f"v{a.version}"
    rec = bundle(ROOT, a.version, out)
    print(
        f"wrote {out}: commit {str(rec['git_commit'])[:12]}{' (dirty)' if rec['git_dirty'] else ''}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
