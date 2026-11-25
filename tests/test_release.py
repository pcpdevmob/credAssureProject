"""Scope #37 release bundle, #41 SBOM and image pinning. No network."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pin_images
import release
import sbom

ROOT = Path(__file__).resolve().parents[1]


def test_scope41_sbom_lists_locked_python_and_npm_packages_not_our_own() -> None:
    doc = sbom.sbom(ROOT)
    assert doc["bomFormat"] == "CycloneDX" and doc["specVersion"] == "1.5"
    purls = {c["purl"] for c in doc["components"]}
    assert any(p.startswith("pkg:pypi/fastapi@") for p in purls)
    assert any(p.startswith("pkg:npm/next@") for p in purls)
    assert not any("credassure" in p for p in purls)  # workspace members are the application
    assert all(c["version"] for c in doc["components"])


def test_scope41_pin_keeps_the_tag_and_skips_pinned_and_variable_refs() -> None:
    text = (
        "FROM node:22-slim AS build\nFROM nginx:1.27@sha256:" + "a" * 64 + "\nFROM ${BASE}\n"
        "services:\n  x:\n    image: redis:7 # cache\n"
    )
    out = pin_images.pin(text, lambda ref: "sha256:" + "b" * 64)
    assert "FROM node:22-slim@sha256:" + "b" * 64 + " AS build" in out
    assert "nginx:1.27@sha256:" + "a" * 64 in out and "FROM ${BASE}" in out
    assert "image: redis:7@sha256:" + "b" * 64 + " # cache" in out
    assert pin_images.unpinned(out) == []


def test_scope37_changelog_section_and_semver() -> None:
    text = (
        "# Changelog\n\n## [Unreleased]\n- x\n\n"
        "## [1.0.0] - 2026-11-18\n### Added\n- y\n\n## [0.1.0]\n- z\n"
    )
    assert release.changelog_section(text, "1.0.0") == "## [1.0.0] - 2026-11-18\n### Added\n- y"
    assert release.changelog_section(text, "2.0.0") is None
    with pytest.raises(SystemExit, match="semver"):
        release.bundle(ROOT, "v1", Path("/nonexistent"))


def test_scope37_bundle_records_hashes_reports_and_sbom(tmp_path: Path) -> None:
    out = tmp_path / "v1.0.0"
    root = tmp_path / "repo"
    for rel in ("uv.lock", "package-lock.json", "pyproject.toml", "evaluation/FROZEN.sha256"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes((ROOT / rel).read_bytes())
    (root / "evaluation/reports").mkdir()
    names = (
        "E4-2026-11-07.md",
        "E4-2026-11-16.md",
        "E13-2026-11-18.md",
        "E4-routes-2026-11-01.md",
        "G4-draft-2026-11-19.md",
        "G4-2026-11-24.md",
    )
    for name in names:
        (root / "evaluation/reports" / name).write_text(name)
    (root / "CHANGELOG.md").write_text("## [1.0.0] - 2026-11-18\n- first\n")
    rec = release.bundle(root, "1.0.0", out)
    assert rec["evaluation_reports"] == {
        "E13": "evaluation/reports/E13-2026-11-18.md",
        "E4": "evaluation/reports/E4-2026-11-16.md",
        "G4": "evaluation/reports/G4-2026-11-24.md",
    }
    assert set(rec["hashes"]) == {"uv.lock", "package-lock.json", "evaluation/FROZEN.sha256"}
    assert (
        json.loads((out / "sbom.cdx.json").read_text())["metadata"]["component"]["version"]
        == "1.0.0"
    )
    assert (out / "reports/E4-2026-11-16.md").exists()
