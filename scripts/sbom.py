"""Software bill of materials (scope #41): CycloneDX 1.5 JSON from the two lock files.

    uv run python scripts/sbom.py --out var/release/sbom.cdx.json

Every locked Python package (uv.lock) and npm package (package-lock.json) becomes one component
with a purl and, where the lock has it, a SHA-256 hash. Workspace members are listed as the
application itself, not as third-party components. Reads only the lock files: no network.
"""

import argparse
import json
import tomllib
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def python_components(lock: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for p in lock.get("package", []):
        src = p.get("source", {})
        if "registry" not in src:  # workspace members and editable paths are ours
            continue
        comp: dict[str, Any] = {
            "type": "library",
            "name": p["name"],
            "version": p["version"],
            "purl": f"pkg:pypi/{p['name']}@{p['version']}",
        }
        sdist = (p.get("sdist") or {}).get("hash", "")
        if sdist.startswith("sha256:"):
            comp["hashes"] = [{"alg": "SHA-256", "content": sdist.removeprefix("sha256:")}]
        out.append(comp)
    return out


def npm_components(lock: dict[str, Any]) -> list[dict[str, Any]]:
    out, seen = [], set()
    for path, p in lock.get("packages", {}).items():
        if "node_modules/" not in path or p.get("link") or "version" not in p:
            continue  # the root, workspace members and their symlinks are ours
        name = path.rsplit("node_modules/", 1)[1]
        key = (name, p["version"])
        if key in seen:
            continue
        seen.add(key)
        scope, _, base = name.rpartition("/")
        purl = (
            f"pkg:npm/{scope.replace('@', '%40')}/{base}@{p['version']}"
            if scope
            else f"pkg:npm/{name}@{p['version']}"
        )
        comp: dict[str, Any] = {
            "type": "library",
            "name": name,
            "version": p["version"],
            "purl": purl,
        }
        if p.get("dev"):
            comp["scope"] = "excluded"  # build and test only, not shipped in the web bundle
        out.append(comp)
    return out


def sbom(root: Path = ROOT, version: str | None = None) -> dict[str, Any]:
    py = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    npm = json.loads((root / "package-lock.json").read_text(encoding="utf-8"))
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    components = sorted(python_components(py) + npm_components(npm), key=lambda c: c["purl"])
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "credassure",
                "version": version or project["version"],
            }
        },
        "components": components,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=ROOT / "var/release/sbom.cdx.json")
    ap.add_argument("--version")
    a = ap.parse_args(argv)
    doc = sbom(ROOT, a.version)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {a.out}: {len(doc['components'])} components")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
