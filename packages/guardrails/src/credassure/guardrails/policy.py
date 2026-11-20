"""Guardrail policy file `config/guardrails.yaml` (ADR 0029 §4, scope #56).

The file is versioned and hashed like the prompt registry. `config/guardrails.lock` maps each
version to the sha256 of the file text; a change without a version bump no longer matches its lock
line and `python -m credassure.guardrails.policy check` (run by `make eval-fast` and a test in
`make check`) fails. `lock` records the current version after a deliberate bump.
"""

import argparse
import hashlib
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[5]
POLICY = ROOT / "config" / "guardrails.yaml"
LOCK = ROOT / "config" / "guardrails.lock"
ACTIONS = frozenset({"block", "redact", "flag", "cap", "pass"})


@dataclass(frozen=True)
class Policy:
    version: str
    sha256: str
    rules: frozenset[str]
    audited_actions: frozenset[str]
    excerpt_limit: int
    full_text_bases: frozenset[str]
    refuse_pii_kinds: frozenset[str]
    protected_tokens: frozenset[str] = frozenset()
    protected_exact: frozenset[str] = frozenset()


def parse(text: str) -> Policy:
    data: Any = yaml.safe_load(text)
    if not isinstance(data, Mapping):
        raise ValueError("guardrails.yaml: not a mapping")
    rules = frozenset(r for rail in data["rails"].values() for r in rail["rules"])
    audited = frozenset(data["audited_actions"])
    if not audited <= ACTIONS or "pass" in audited:
        raise ValueError(
            "guardrails.yaml: audited_actions must be a subset of the actions, never pass"
        )
    return Policy(
        version=str(data["version"]),
        sha256=hashlib.sha256(text.encode()).hexdigest(),
        rules=rules,
        audited_actions=audited,
        excerpt_limit=int(data["excerpt"]["limit"]),
        full_text_bases=frozenset(data["excerpt"]["full_text_bases"]),
        refuse_pii_kinds=frozenset(data["upload"]["refuse_pii_kinds"]),
        protected_tokens=frozenset(data.get("protected_attributes", {}).get("tokens", [])),
        protected_exact=frozenset(data.get("protected_attributes", {}).get("exact", [])),
    )


@cache
def load() -> Policy:
    return parse(POLICY.read_text(encoding="utf-8"))


def _locked() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in LOCK.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            version, sha = line.split()
            out[version] = sha
    return out


def violations() -> list[str]:
    p = parse(POLICY.read_text(encoding="utf-8"))
    locked = _locked()
    if p.version not in locked:
        return [
            f"version {p.version} is not in {LOCK.name}: run `policy lock` after a deliberate bump"
        ]
    if locked[p.version] != p.sha256:
        return [f"guardrails.yaml changed without a version bump (was {p.version})"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="credassure.guardrails.policy")
    parser.add_argument("command", choices=["check", "lock"])
    args = parser.parse_args(argv)
    if args.command == "lock":
        p = parse(POLICY.read_text(encoding="utf-8"))
        locked = _locked() if LOCK.exists() else {}
        if p.version in locked and locked[p.version] != p.sha256:
            print(f"version {p.version} is already locked to other text: bump it", file=sys.stderr)
            return 1
        locked[p.version] = p.sha256
        body = "".join(f"{v} {s}\n" for v, s in sorted(locked.items()))
        LOCK.write_text("# version sha256 of config/guardrails.yaml (ADR 0029)\n" + body)
        return 0
    bad = violations()
    for b in bad:
        print(b, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
