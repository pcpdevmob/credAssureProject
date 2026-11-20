"""Pin every base and service image to its registry digest (scope #41).

    make pin-images            # needs Docker and registry access; rewrites the files in place
    make pin-images ARGS=--check   # exit 1 if any image is unpinned (no network)

Rewrites `FROM image:tag` in deploy/docker/* and `image: image:tag` in deploy/compose/*.yaml to
`image:tag@sha256:<digest>`, keeping the tag so a reader still sees the version. Digests come
from `docker buildx imagetools inspect`, the multi-arch index digest, so the same pin works on
the Mac (arm64) and in CI (amd64).
"""

import argparse
import re
import subprocess  # nosec B404 - fixed argv, no shell
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROM = re.compile(r"^(FROM\s+)(?P<ref>\S+)(?P<rest>.*)$", re.M)
IMAGE = re.compile(r"^(\s*image:\s*)(?P<ref>[^\s#]+)(?P<rest>.*)$", re.M)


def files(root: Path) -> list[Path]:
    return sorted((root / "deploy/docker").glob("Dockerfile*")) + sorted(
        (root / "deploy/compose").glob("*.yaml")
    )


def docker_digest(ref: str) -> str:
    argv = ["docker", "buildx", "imagetools", "inspect", "--format", "{{json .Manifest.Digest}}"]
    out = subprocess.run(  # noqa: S603  # nosec B603 B607 - fixed argv; ref after "--"
        [*argv, "--", ref],  # docker from PATH, as the Makefile runs it
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    ).stdout
    digest = out.strip().strip('"')
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise SystemExit(f"no digest for {ref}: {out!r}")
    return digest


def unpinned(text: str) -> list[str]:
    refs = [m["ref"] for rx in (FROM, IMAGE) for m in rx.finditer(text)]
    return [r for r in refs if "@sha256:" not in r and "$" not in r]


def pin(text: str, resolve: Callable[[str], str]) -> str:
    def sub(m: re.Match[str]) -> str:
        ref = m["ref"]
        if "@sha256:" in ref or "$" in ref:
            return m.group(0)
        return f"{m.group(1)}{ref}@{resolve(ref)}{m['rest']}"

    return IMAGE.sub(sub, FROM.sub(sub, text))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    left = {str(f.relative_to(ROOT)): unpinned(f.read_text()) for f in files(ROOT)}
    left = {k: v for k, v in left.items() if v}
    if a.check:
        for f, refs in left.items():
            print(f"{f}: unpinned {', '.join(refs)}")
        return 1 if left else 0
    cache: dict[str, str] = {}
    for f in files(ROOT):
        text = f.read_text()
        new = pin(text, lambda r: cache.setdefault(r, docker_digest(r)))
        if new != text:
            f.write_text(new)
            print(f"pinned {f.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
