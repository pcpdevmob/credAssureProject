"""Blind pooled judgement for the KR-05 retrieval labels (E8 M1).

`pool`: the union of every query's top 5 over all 18 configurations, deduplicated by (document, section)
and shuffled within each query. No configuration, rank or existing label is written anywhere, so
the judges cannot tell where a passage came from. Criteria and judges: evaluation/retrieval/v1/judging/criteria.md.

`make retrieval-pool` → evaluation/retrieval/v1/judging/{pool.jsonl,judging_sheet.csv}
`make judge JUDGE=<name> [SAMPLE=0.25]` → judging/judgments_<name>.jsonl (method: judging/README.md)
"""

import argparse
import csv
import json
import os
import random
import re
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .gold.data import REPO
from .retrieval_eval import Hits, _ws, load_queries, open_searcher, run_searches

JUDGING = REPO / "evaluation" / "retrieval" / "v1" / "judging"
COLUMNS = [
    "item_id",
    "query_id",
    "query",
    "doc_id",
    "title",
    "section_path",
    "passage",
    "judge_A",
    "judge_A_note",
    "judge_B",
    "judge_B_note",
    "adjudicated",
    "adjudicator_note",
]
CELL_MAX = 32_000  # spreadsheet cell limit


def build_pool(
    hits: Hits, queries: list[dict[str, Any]], seed: str, depth: int = 5
) -> list[dict[str, str]]:
    """One row per distinct (query, document, section) in any top `depth`; the longest text is kept."""
    best: dict[tuple[str, str, str], Any] = {}
    for by_q in hits.values():
        for q in queries:
            for p in by_q[q["id"]][:depth]:
                key = (q["id"], p.doc_id, _ws(p.section_path or ""))
                if key not in best or len(p.text) > len(best[key].text):
                    best[key] = p
    text = {q["id"]: q["query"] for q in queries}
    rows: list[dict[str, str]] = []
    rng = random.Random(f"{seed}:judging")  # noqa: S311  # nosec B311 — order only
    for q in queries:
        group = [
            {
                "query_id": q["id"],
                "query": text[q["id"]],
                "doc_id": p.doc_id,
                "title": p.title,
                "section_path": p.section_path or "",
                "passage": p.text[:CELL_MAX],
            }
            for (qid, _, _), p in sorted(best.items(), key=lambda kv: kv[0])
            if qid == q["id"]
        ]
        rng.shuffle(group)
        rows += group
    return [{"item_id": f"J{i:04d}", **r} for i, r in enumerate(rows, 1)]


def write_pool(rows: list[dict[str, str]], out: Path = JUDGING) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "pool.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    with (out / "judging_sheet.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLUMNS, restval="")
        w.writeheader()
        w.writerows(rows)


LABELS = {"2": 2, "1": 1, "0": 0}  # relevant / partially relevant / not relevant
PASSAGE_SHOWN = 1_200
PROMPT = "[2] relevant  [1] partial  [0] not relevant  [s]kip  [b]ack  [c]riteria  [q]uit > "


def load_pool(path: Path = JUDGING / "pool.jsonl") -> list[dict[str, str]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def agreement_sample(items: list[dict[str, str]], seed: str, frac: float) -> list[dict[str, str]]:
    """Pre-registered subset for the second judge: same seed → same items, pool order kept."""
    rng = random.Random(f"{seed}:agreement")  # noqa: S311  # nosec B311 — sampling only
    picked = set(rng.sample(sorted(r["item_id"] for r in items), round(len(items) * frac)))
    return [r for r in items if r["item_id"] in picked]


def load_judgments(path: Path) -> dict[str, int]:
    """Latest answer per item wins, so going back and re-answering only appends."""
    latest: dict[str, int] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                latest[rec["item_id"]] = rec["label"]
    return latest


def screen(r: Mapping[str, str], i: int, n: int, judged: int, previous: int | None) -> str:
    """Query, title, section and passage only: no configuration, rank or existing label."""
    earlier = f"(your earlier answer: {previous})\n" if previous is not None else ""
    return (
        f"\n{'─' * 72}\nitem {i + 1} of {n} · judged {judged}\n\n"
        f"QUERY:   {r['query']}\nDOC:     {r['title']}\nSECTION: {r['section_path'] or '—'}\n\n"
        f"{r['passage'][:PASSAGE_SHOWN]}\n\n{earlier}{PROMPT}"
    )


def judge(
    items: list[dict[str, str]],
    out: Path,
    judge_name: str,
    read_key: Callable[[], str],
    write: Callable[[str], object],
    criteria: str = "",
) -> int:
    """Resumable single-judge loop; every answer is appended and flushed before the next item."""
    done = load_judgments(out)
    i = next((n for n, r in enumerate(items) if r["item_id"] not in done), len(items))
    with out.open("a", encoding="utf-8") as f:
        while i < len(items):
            r = items[i]
            judged = sum(x["item_id"] in done for x in items)
            write(screen(r, i, len(items), judged, done.get(r["item_id"])))
            key = read_key()
            if key in LABELS:
                rec = {
                    "item_id": r["item_id"],
                    "judge": judge_name,
                    "label": LABELS[key],
                    "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                }
                f.write(json.dumps(rec) + "\n")
                f.flush()
                done[r["item_id"]] = LABELS[key]
                i += 1
            elif key == "s":
                i += 1
            elif key == "b":
                i = max(0, i - 1)
            elif key == "c":
                write("\n" + criteria)
            elif key == "q":
                break
    judged = sum(x["item_id"] in done for x in items)
    write(f"\nsaved: {judged} of {len(items)} judged → {out}\n")
    return judged


def read_key() -> str:
    """One keypress on a terminal; a line when piped (EOF → quit)."""
    if not sys.stdin.isatty():
        return sys.stdin.readline().strip()[:1] or "q"
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def judge_main(argv: list[str], env: Mapping[str, str]) -> int:
    ap = argparse.ArgumentParser(prog="make judge")
    ap.add_argument("--judge", required=True)
    ap.add_argument("--sample", type=float, help="agreement subset fraction, e.g. 0.25")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[a-z]+", args.judge):  # used in a file name
        print("judge name: lowercase letters only", file=sys.stderr)
        return 2
    items = load_pool()
    if args.sample:
        items = agreement_sample(items, env.get("CREDASSURE_SEED", "20261026"), args.sample)
    criteria = (JUDGING / "criteria.md").read_text(encoding="utf-8")
    judge(
        items,
        JUDGING / f"judgments_{args.judge}.jsonl",
        args.judge,
        read_key,
        lambda s: print(s, end="", flush=True),
        criteria,
    )
    return 0


def main(argv: list[str], env: Mapping[str, str] = os.environ) -> int:
    if argv[:1] == ["judge"]:
        return judge_main(argv[1:], env)
    if argv[:1] != ["pool"]:
        print(
            "usage: python -m credassure.evaluation.retrieval_judging pool | judge --judge NAME",
            file=sys.stderr,
        )
        return 2
    searcher, _, reranker, _ = open_searcher(env)
    queries = load_queries()
    hits = run_searches(
        searcher,
        queries,
        rerank_options=(False, True) if reranker else (False,),
        progress=lambda line: print(line, file=sys.stderr, flush=True),
    )
    if len(hits) != 18:
        print(
            f"retrieval-pool: {len(hits)} configurations, need 18 (rerank extra?)", file=sys.stderr
        )
        return 1
    rows = build_pool(hits, queries, env.get("CREDASSURE_SEED", "20261026"))
    write_pool(rows)
    per_q = [sum(r["query_id"] == q["id"] for r in rows) for q in queries]
    print(f"retrieval-pool: {len(rows)} items, {min(per_q)}-{max(per_q)} per query → {JUDGING}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
