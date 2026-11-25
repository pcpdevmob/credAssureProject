"""Retrieval ladder and answerability curve (plan v3.4 P4, scope #61, #62, #63, KR-05).

Rungs: 0 baseline index · 1 contextual chunk headers (one re-ingest with RETRIEVAL_CONTEXT_HEADERS)
· 2 + glossary rewrite · 3 + reranker. Each rung is measured on the frozen 40 (v1.0 labels, reported
only) and on the dev split, with recall@5 (a relevant passage in the top 5, section level) and MRR@10.

The answerability threshold is chosen on the dev split ONLY (20 answerable queries plus the
dev-only unanswerable set), never on the frozen 40 or the 100-item test set (plan v3.4).
Rule: the highest top-score threshold with at most MAX_FALSE_ABSTAIN answerable dev queries
abstaining, maximising correctly abstained dev negatives; ties keep the lower threshold.

    python -m credassure.evaluation.retrieval_ladder run --rung 0 --label baseline [--rewrite] [--rerank]
    python -m credassure.evaluation.retrieval_ladder curve
    python -m credassure.evaluation.retrieval_ladder report
"""

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .gold.data import REPO
from .retrieval_eval import filters_for, is_relevant, load_queries

DEV = REPO / "evaluation" / "retrieval" / "dev" / "queries.jsonl"
DEV_NEG = DEV.with_name("unanswerable.jsonl")
DATA = REPO / "evaluation" / "reports" / "retrieval-ladder.json"
MAX_FALSE_ABSTAIN = 1  # of the 20 answerable dev queries (5%)


def recall_and_mrr(
    ranked: Mapping[str, Sequence[Any]], queries: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """recall@5 count and MRR@10 over `queries`; `ranked[qid]` is a list of passages in rank order."""
    hits5, rr = 0, 0.0
    for q in queries:
        found = list(ranked.get(q["id"], []))[:10]
        ranks = [i for i, p in enumerate(found, 1) if is_relevant(p, q, section=True)]
        hits5 += bool(ranks and ranks[0] <= 5)
        rr += 1.0 / ranks[0] if ranks else 0.0
    n = len(queries)
    return {"recall5": hits5, "n": n, "mrr10": round(rr / n, 4) if n else 0.0}


def choose_threshold(
    positive: Sequence[float], negative: Sequence[float], max_false: int = MAX_FALSE_ABSTAIN
) -> tuple[float | None, list[dict[str, Any]]]:
    """(threshold or None, curve). A query abstains when its top score is below the threshold."""
    candidates = sorted({*positive, *negative})
    curve, best, best_key = [], None, (-1, 0.0)
    for t in candidates:
        false_abstain = sum(s < t for s in positive)
        caught = sum(s < t for s in negative)
        curve.append({"threshold": round(t, 4), "false_abstain": false_abstain, "caught": caught})
        if false_abstain <= max_false and (caught, -t) > best_key:
            best, best_key = t, (caught, -t)
    return (round(best, 4) if best is not None and best_key[0] > 0 else None), curve


def _load(path: Path = DATA) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"rungs": []}


def _save(data: Mapping[str, Any], path: Path = DATA) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _search(searcher: Any, q: Mapping[str, Any], rerank: bool) -> list[Any]:
    return [
        p
        for p, _ in searcher.scored(
            q["query"], filters=filters_for(q), strategy="section", k=10, rerank=rerank
        )
    ]


def run_rung(
    env: Mapping[str, str], rung: int, label: str, *, rewrite: bool, rerank: bool
) -> dict[str, Any]:
    from .retrieval_eval import open_searcher

    searcher, _, has_reranker, _ = open_searcher(env)
    searcher.query_rewrite = rewrite
    use_rerank = rerank and has_reranker
    frozen, dev = load_queries(), load_queries(DEV)
    record = {
        "rung": rung,
        "label": label,
        "date": datetime.now(UTC).date().isoformat(),
        "flags": {
            "contextual_headers": env.get("RETRIEVAL_CONTEXT_HEADERS", "false").lower() == "true",
            "query_rewrite": rewrite,
            "rerank": use_rerank,
        },
        "frozen_v1.0": recall_and_mrr(
            {q["id"]: _search(searcher, q, use_rerank) for q in frozen}, frozen
        ),
        "dev": recall_and_mrr({q["id"]: _search(searcher, q, use_rerank) for q in dev}, dev),
    }
    data = _load()
    data["rungs"] = [r for r in data["rungs"] if r["rung"] != rung] + [record]
    _save(data)
    return record


def run_curve(env: Mapping[str, str]) -> dict[str, Any]:
    from .retrieval_eval import open_searcher

    searcher, _, has_reranker, _ = open_searcher(env)
    if not has_reranker:
        raise SystemExit("curve needs the reranker (install the `rerank` extra)")
    searcher.query_rewrite = env.get("RETRIEVAL_QUERY_REWRITE", "false").lower() == "true"
    filters_q = load_queries(DEV)[0]  # same as_of, home state and lender type as the dev split

    def top(q: Mapping[str, Any]) -> float:
        got = searcher.scored(
            q["query"], filters=filters_for({**filters_q, **q}), strategy="section", k=1
        )
        return float(got[0][1]) if got and got[0][1] is not None else float("-inf")

    pos = [top(q) for q in load_queries(DEV)]
    neg = [top(q) for q in load_queries(DEV_NEG)]
    threshold, curve = choose_threshold(pos, neg)
    data = _load()
    result: dict[str, Any] = {
        "chosen_on": "dev split only (20 answerable + dev unanswerable)",
        "threshold": threshold,
        "max_false_abstain": MAX_FALSE_ABSTAIN,
        "curve": curve,
    }
    data["answerability"] = result
    _save(data)
    return result


def render(data: Mapping[str, Any]) -> str:
    lines = [
        "# Retrieval ladder (plan v3.4 P4)",
        "",
        "Section chunks, hybrid search, top 10. recall@5 = queries with a relevant passage in the top 5.",
        "Frozen 40 (v1.0 labels) are reported only; every choice was made on the dev split.",
        "",
        "| Rung | Label | Headers | Rewrite | Rerank | Frozen recall@5 | Frozen MRR@10 | Dev recall@5 | Dev MRR@10 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(data.get("rungs", []), key=lambda r: r["rung"]):
        f, d, fl = r["frozen_v1.0"], r["dev"], r["flags"]
        lines.append(
            f"| {r['rung']} | {r['label']} | {fl['contextual_headers']} | {fl['query_rewrite']} | "
            f"{fl['rerank']} | {f['recall5']}/{f['n']} | {f['mrr10']} | {d['recall5']}/{d['n']} | {d['mrr10']} |"
        )
    a = data.get("answerability")
    if a:
        lines += [
            "",
            "## Answerability threshold (dev only)",
            "",
            f"Chosen: **{a['threshold']}** "
            f"(at most {a['max_false_abstain']} answerable dev query abstains).",
            "",
            "| Threshold | Answerable abstained | Unanswerable caught |",
            "|---|---|---|",
        ]
        lines += [
            f"| {c['threshold']} | {c['false_abstain']} | {c['caught']} |" for c in a["curve"]
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None, env: Mapping[str, str] = os.environ) -> int:
    parser = argparse.ArgumentParser(prog="retrieval_ladder")
    sub = parser.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--rung", type=int, required=True, choices=[0, 1, 2, 3])
    r.add_argument("--label", required=True)
    r.add_argument("--rewrite", action="store_true")
    r.add_argument("--rerank", action="store_true")
    sub.add_parser("curve")
    sub.add_parser("report")
    args = parser.parse_args(argv)
    if args.cmd == "run":
        print(
            json.dumps(
                run_rung(env, args.rung, args.label, rewrite=args.rewrite, rerank=args.rerank)
            )
        )
    elif args.cmd == "curve":
        print(json.dumps({k: v for k, v in run_curve(env).items() if k != "curve"}))
    else:
        out = (
            REPO
            / "evaluation"
            / "reports"
            / f"retrieval-ladder-{datetime.now(UTC).date().isoformat()}.md"
        )
        out.write_text(render(_load()), encoding="utf-8")
        print(f"retrieval-ladder: wrote {out.relative_to(REPO)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
