"""Blind pooled judgement for the KR-05 retrieval labels (E8 M1).

`pool`: the union of every query's top 10 over all 18 configurations, deduplicated by (document, section)
and shuffled within each query. No configuration, rank or existing label is written anywhere, so
the judges cannot tell where a passage came from. Criteria and judges: evaluation/retrieval/v1/judging/criteria.md.

`make retrieval-pool` → evaluation/retrieval/v1/judging/{pool.jsonl,judging_sheet.csv}
"""

import csv
import json
import os
import random
import sys
from collections.abc import Mapping
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


def build_pool(hits: Hits, queries: list[dict[str, Any]], seed: str) -> list[dict[str, str]]:
    """One row per distinct (query, document, section); the longest text of the duplicates is kept."""
    best: dict[tuple[str, str, str], Any] = {}
    for by_q in hits.values():
        for q in queries:
            for p in by_q[q["id"]]:
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


def main(argv: list[str], env: Mapping[str, str] = os.environ) -> int:
    if argv[:1] != ["pool"]:
        print("usage: python -m credassure.evaluation.retrieval_judging pool", file=sys.stderr)
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
