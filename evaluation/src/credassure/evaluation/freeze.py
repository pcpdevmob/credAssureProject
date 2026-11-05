"""G1 freeze manifest for the evaluation assets and synthetic data v1.

``--write`` records SHA-256 of every frozen asset in evaluation/FROZEN.sha256 (run by /freeze-g1 only after the
owner confirms); ``--verify-only`` checks it. The FROZEN marker files are written by /freeze-g1, not here.
"""

import argparse
import hashlib
import sys

from . import check_corpus_refs
from .gold.data import REPO

ASSETS = (
    "evaluation/testset/v1/items.jsonl",
    "evaluation/retrieval/v1/queries.jsonl",
    "evaluation/redteam/prompts.jsonl",
    "evaluation/fixtures/v1/bad_citations.jsonl",
    "evaluation/gold/fixtures/rbi_kfs_apr_illustration.yaml",
    "data/frozen/v1/SHA256SUMS",
)
MANIFEST = REPO / "evaluation" / "FROZEN.sha256"


def digests() -> str:
    return "".join(f"{hashlib.sha256((REPO / p).read_bytes()).hexdigest()}  {p}\n" for p in ASSETS)


def verify() -> list[str]:
    """Paths whose bytes differ from the frozen manifest (empty when there is no manifest yet)."""
    if not MANIFEST.exists():
        return []
    frozen = dict(
        line.split("  ", 1)[::-1] for line in MANIFEST.read_text(encoding="utf-8").splitlines()
    )
    now = dict(line.split("  ", 1)[::-1] for line in digests().splitlines())
    return sorted(p for p in frozen if frozen[p] != now.get(p))


def readiness() -> list[str]:
    """Items and queries G1 may not freeze with: unknown doc_ids, any cited document not yet available
    (status ok/ok_manual with extracted text), or a regulatory key fact missing from its cited text."""
    return check_corpus_refs.check(strict=True).failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m credassure.evaluation.freeze")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--verify-only", action="store_true")
    group.add_argument("--readiness", action="store_true")
    args = parser.parse_args(argv)
    if args.write:
        if blocked := readiness():
            print("Not ready to freeze; replace or wait for:", *blocked, sep="\n  ")
            return 1
        MANIFEST.write_text(digests(), encoding="utf-8", newline="\n")
        print(f"wrote {MANIFEST}")
        return 0
    if args.readiness:
        blocked = readiness()
        print("\n".join(blocked) or "all cited documents are available and support their gold")
        return 1 if blocked else 0
    drift = verify()
    for path in drift:
        print(f"CHANGED {path}", file=sys.stderr)
    print("frozen assets verified" if not drift else f"{len(drift)} frozen assets changed")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
