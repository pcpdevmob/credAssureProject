"""Corpus-reference guard (KR-04, KR-05, BRD §13): every document the eval assets cite must be real and usable.

Checks every doc_id in retrieval labels, KR-04 ``must_not_cite`` lists and regulatory gold:
- the doc_id exists in data/corpus/manifest.yaml (or is a synthetic POL-/FAQ-/KFS- file): else FAIL;
- the document is available (lock status ok/ok_manual and extracted text present): else "awaiting corpus",
  which fails only with ``--strict`` (the G1 freeze);
- for regulatory items whose cited documents are all available, each gold key fact appears in at least one
  of them: else FAIL (while any is pending the item is only "awaiting corpus").

``make check`` runs it non-strict; ``freeze --write`` runs it strict and lists the items to replace.
"""

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .gold.data import DATA, REPO

ASSETS = ("evaluation/testset/v1/items.jsonl", "evaluation/retrieval/v1/queries.jsonl")
SYNTHETIC = ("kfs", "policies")


@dataclass
class Corpus:
    manifest: Path = REPO / "data" / "corpus" / "manifest.yaml"
    lock: Path = REPO / "data" / "corpus" / "manifest.lock.json"
    text: Path = REPO / "data" / "corpus" / "text"
    synthetic: Path = DATA

    def synthetic_files(self) -> dict[str, Path]:
        return {p.stem: p for folder in SYNTHETIC for p in (self.synthetic / folder).glob("*.md")}

    def known(self) -> set[str]:
        docs = yaml.safe_load(self.manifest.read_text(encoding="utf-8"))["documents"]
        return {d["doc_id"] for d in docs} | set(self.synthetic_files())

    def texts(self) -> dict[str, Path]:
        """doc_id -> text file, for available documents only."""
        lock = json.loads(self.lock.read_text(encoding="utf-8"))
        real = {
            doc_id: self.text / f"{doc_id}.txt"
            for doc_id, entry in lock.items()
            if entry.get("status") in {"ok", "ok_manual"} and (self.text / f"{doc_id}.txt").exists()
        }
        return real | self.synthetic_files()


def known_doc_ids() -> set[str]:
    return Corpus().known()


_UNITS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = ["_", "_", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
_NUM = {w: i for i, w in enumerate(_UNITS)} | {w: 10 * i for i, w in enumerate(_TENS) if w != "_"}
_WORDS = "|".join(sorted([*_NUM, "hundred"], key=len, reverse=True))
_NUM_RUN = re.compile(rf"\b(?:{_WORDS})(?:[\s-]+(?:and\s+)?(?:{_WORDS}))*\b")


def _number(match: re.Match[str]) -> str:
    total = 0
    for word in re.split(r"[\s-]+", match.group(0)):
        if word == "hundred":
            total = max(total, 1) * 100
        elif word != "and":
            total += _NUM[word]
    return str(total)


def _norm(text: str) -> str:
    # Gazette notifications spell amounts out ("twenty five crore"); key facts use digits.
    # ponytail: below a thousand only, which covers crore/lakh multipliers; "one" in prose also becomes "1".
    return _NUM_RUN.sub(_number, re.sub(r"\s+", " ", text).casefold())


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    awaiting: list[str] = field(default_factory=list)


def _rows(repo: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for path in ASSETS
        for line in (repo / path).read_text(encoding="utf-8").splitlines()
    ]


def check(
    corpus: Corpus | None = None, rows: list[dict[str, Any]] | None = None, strict: bool = False
) -> Report:
    corpus = corpus or Corpus()
    rows = _rows(REPO) if rows is None else rows
    known, texts, report = corpus.known(), corpus.texts(), Report()
    cache: dict[str, str] = {}

    def text(doc_id: str) -> str:
        if doc_id not in cache:
            cache[doc_id] = _norm(texts[doc_id].read_text(encoding="utf-8", errors="replace"))
        return cache[doc_id]

    for row in rows:
        gold = row.get("gold", row)
        relevant = list(gold.get("relevant_doc_ids", []))
        cited = relevant + list(gold.get("must_not_cite", []))
        if unknown := [d for d in cited if d not in known]:
            report.failures.append(f"{row['id']}: not in manifest: {', '.join(unknown)}")
        pending = [d for d in cited if d in known and d not in texts]
        if pending:
            (report.failures if strict else report.awaiting).append(
                f"{row['id']}: awaiting corpus: {', '.join(pending)}"
            )
        if row.get("category") != "regulatory" or not relevant:
            continue
        if any(d not in texts for d in relevant):
            continue  # the fact may be in a pending document; checked once all are available
        have = relevant
        for fact in gold.get("key_facts", []):
            if not any(_norm(fact) in text(d) for d in have):
                report.failures.append(
                    f"{row['id']}: key fact {fact!r} not found in {', '.join(have)}"
                )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m credassure.evaluation.check_corpus_refs")
    parser.add_argument("--strict", action="store_true", help="pending documents fail (G1 freeze)")
    args = parser.parse_args(argv)
    report = check(strict=args.strict)
    for line in report.awaiting:
        print(f"AWAITING {line}")
    for line in report.failures:
        print(f"FAIL     {line}")
    print(
        f"corpus refs: {len(report.failures)} failures, {len(report.awaiting)} items awaiting corpus"
    )
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
