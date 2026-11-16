"""Prompt registry (scope #36, ARCHITECTURE §8.6).

Every model prompt is a YAML file `<name>.yaml` in a `prompts/` folder of a `credassure.*` package
(agents keep theirs beside their code): `name`, semantic `version`, `template` ($slot syntax),
optional `examples`, optional `max_tokens` (output cap for this prompt). The file's sha256
and version go on every `llm` span, into
`AgentResult.prompt_versions` and into the eval reproducibility record.

`make eval-fast` runs `python -m credassure.core.prompts check --base <ref>`: any prompt file
whose text changed without a higher version fails the check.
"""

import argparse
import hashlib
import re
import subprocess  # nosec B404 - fixed git argv only
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from string import Template
from typing import Any

import yaml

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    template: str
    examples: tuple[str, ...]
    sha256: str
    max_tokens: int | None = None  # per-prompt output cap; the client also applies LLM_MAX_TOKENS

    def render(self, **slots: Any) -> str:
        return Template(self.template).substitute(slots)


def _parse(text: str, stem: str) -> Prompt:
    data = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise ValueError(f"{stem}: not a mapping")
    if data.get("name") != stem:
        raise ValueError(f"{stem}: name must match the file name")
    if not _SEMVER.match(str(data.get("version", ""))):
        raise ValueError(f"{stem}: version must be MAJOR.MINOR.PATCH")
    if not isinstance(data.get("template"), str):
        raise ValueError(f"{stem}: template is required")
    cap = data.get("max_tokens")
    if cap is not None and (not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0):
        raise ValueError(f"{stem}: max_tokens must be a positive integer")
    return Prompt(
        name=stem,
        version=str(data["version"]),
        template=data["template"],
        examples=tuple(str(e) for e in data.get("examples") or ()),
        sha256=hashlib.sha256(text.encode()).hexdigest(),
        max_tokens=cap,
    )


def load_file(path: Path) -> Prompt:
    return _parse(path.read_text(encoding="utf-8"), path.stem)


@cache
def registry() -> dict[str, Prompt]:
    """Every prompt shipped in any `credassure.*` package (editable or installed)."""
    import credassure

    found: dict[str, Prompt] = {}
    for base in credassure.__path__:
        for path in sorted(Path(base).rglob("prompts/*.yaml")):
            p = load_file(path)
            if p.name in found:
                raise ValueError(f"duplicate prompt name {p.name}")
            found[p.name] = p
    return found


def prompt_version(name: str) -> str:
    p = registry().get(name)
    return p.version if p else "unversioned"


def prompt_max_tokens(name: str) -> int | None:
    p = registry().get(name)
    return p.max_tokens if p else None


def prompt_sha(name: str) -> str | None:
    p = registry().get(name)
    return p.sha256 if p else None


def versions() -> dict[str, str]:
    return {name: p.version for name, p in sorted(registry().items())}


def _ver(text: str) -> tuple[int, ...]:
    m = _SEMVER.match(str((yaml.safe_load(text) or {}).get("version", "")))
    return tuple(int(g) for g in m.groups()) if m else (-1,)


def bump_violations(changes: Iterable[tuple[str, str | None, str | None]]) -> list[str]:
    """(path, old text, new text) per changed prompt file → files changed without a version bump."""
    return [
        path
        for path, old, new in changes
        if old is not None and new is not None and old != new and _ver(new) <= _ver(old)
    ]


def _git(*args: str) -> str:
    return subprocess.run(  # noqa: S603  # nosec B603 B607 - fixed git argv, git from PATH
        ["git", *args],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def _show(ref: str, path: str) -> str | None:
    try:
        return _git("show", f"{ref}:{path}")
    except subprocess.CalledProcessError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="credassure.core.prompts")
    parser.add_argument("command", choices=["check"])
    parser.add_argument("--base", required=True, help="git ref to compare against")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[\w./~^@{}-]+", args.base) or args.base.startswith("-"):
        parser.error("--base must be a git ref or SHA")
    changed = [
        p
        for p in _git("diff", "--name-only", f"{args.base}...HEAD", "--").splitlines()
        if re.search(r"/prompts/[^/]+\.yaml$", p)
    ]
    bad = bump_violations((p, _show(args.base, p), _show("HEAD", p)) for p in changed)
    for path in bad:
        print(f"{path}: prompt changed without a version bump (scope #36)", file=sys.stderr)
    for p in registry().values():  # every shipped prompt must still parse
        print(f"{p.name} {p.version} {p.sha256[:12]}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
