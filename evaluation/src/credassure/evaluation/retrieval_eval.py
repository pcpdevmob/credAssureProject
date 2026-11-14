"""Retrieval evaluation (KR-01..05): keyword, dense and hybrid, by 3 chunkings, rerank off/on, over the
40 labelled queries, measured apart from answer quality.

recall@k here is the BRD measure: the share of queries with at least one relevant passage in the
top k. A passage is relevant when its document is labelled for the query and its section_path starts
with the labelled section, or one of its segments does (DATA_SPEC §7); doc-level numbers are shown next to it so the gap is visible.

KR-04: every passage returned by any configuration is re-checked against its document row: in force on
the as-of date, not superseded, jurisdiction IN or the home state, applies_to all or the lender type,
not another case's KFS, and never in the query's must_not_cite list.

`make retrieval-eval` → evaluation/reports/retrieval-<date>.md
"""

import json
import os
import sqlite3
import sys
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from credassure.retrieval.chunking import STRATEGIES
from credassure.retrieval.search import Filters, Passage, Searcher

from .check_corpus_refs import check
from .gold.data import REPO

MODES = ("keyword", "dense", "hybrid")
QUERIES = REPO / "evaluation" / "retrieval" / "v1" / "queries.jsonl"
TARGET = 34


def load_queries(path: Path = QUERIES) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def filters_for(q: Mapping[str, Any]) -> Filters:
    f = q["filters"]
    return Filters(
        as_of=date.fromisoformat(f["as_of"]),
        home_state=f.get("home_state", "IN-MH"),
        lender_type=f.get("lender_type", "commercial_bank"),
    )


def _ws(text: str) -> str:
    return " ".join(text.split()).casefold()


def section_match(path: str | None, label: str) -> bool:
    """The label starts the path or one of its " > " segments ("" = anywhere in the document), so
    noisy parent headings (Gazette banners) do not break a label."""
    norm, want = _ws(path or ""), _ws(label)
    return norm.startswith(want) or any(seg.startswith(want) for seg in norm.split(" > "))


def is_relevant(p: Passage, q: Mapping[str, Any], *, section: bool) -> bool:
    if not section or not q.get("relevant_sections"):
        return p.doc_id in q["relevant_doc_ids"]
    return any(
        p.doc_id == s["doc_id"] and section_match(p.section_path, s["section_path"])
        for s in q["relevant_sections"]
    )


def kr04_violation(
    doc: Mapping[str, Any],
    q: Mapping[str, Any],
    docs: Mapping[str, Mapping[str, Any]] | None = None,
) -> str | None:
    """Why `doc` must not be cited as current for `q`, or None. Independent of the search SQL."""
    f, case_id = q["filters"], q["filters"].get("case_id")
    if doc["doc_id"] in q.get("must_not_cite", []):
        return "must_not_cite"
    if not doc["effective_from"] or doc["effective_from"] > f["as_of"]:
        return "not_yet_in_force"
    if doc["superseded_by"]:  # superseded once the replacement is in force (unknown = in force)
        rep = (docs or {}).get(doc["superseded_by"])
        if not rep or not rep["effective_from"] or rep["effective_from"] <= f["as_of"]:
            return "superseded"
    if doc["jurisdiction"] not in ("IN", f.get("home_state", "IN-MH")):
        return "other_state"
    if doc["applies_to"] not in ("all", f.get("lender_type", "commercial_bank")):
        return "other_lender_type"
    if doc["case_id"] and (doc["case_id"], doc.get("tenant_id")) != (case_id, f.get("tenant_id")):
        return "other_case"
    return None


@dataclass
class Row:
    strategy: str
    mode: str
    rerank: bool
    hits5: set[str] = field(default_factory=set)
    hits10: set[str] = field(default_factory=set)
    doc_hits5: set[str] = field(default_factory=set)


def evaluate(
    searcher: Searcher,
    queries: list[dict[str, Any]],
    docs: Mapping[str, Mapping[str, Any]],
    *,
    rerank_options: Iterable[bool] = (False,),
    progress: Callable[[str], None] | None = None,
) -> tuple[list[Row], list[str]]:
    rows, violations = [], []
    for strategy in STRATEGIES:
        for mode in MODES:
            for rerank in rerank_options:
                row = Row(strategy, mode, rerank)
                for q in queries:
                    hits = searcher.search_knowledge(
                        q["query"],
                        case_id=q["filters"].get("case_id"),
                        tenant_id=q["filters"].get("tenant_id"),
                        filters=filters_for(q),
                        strategy=strategy,
                        mode=mode,  # type: ignore[arg-type]
                        k=10,
                        rerank=rerank,
                    )
                    if any(is_relevant(p, q, section=True) for p in hits[:5]):
                        row.hits5.add(q["id"])
                    if any(is_relevant(p, q, section=True) for p in hits):
                        row.hits10.add(q["id"])
                    if any(is_relevant(p, q, section=False) for p in hits[:5]):
                        row.doc_hits5.add(q["id"])
                    for p in hits:
                        if why := kr04_violation(docs[p.doc_id], q, docs):
                            violations.append(f"{q['id']} {strategy}/{mode}: {p.doc_id} ({why})")
                rows.append(row)
                if progress:
                    progress(f"{strategy}/{mode}/rerank={rerank}: {len(row.hits5)}/{len(queries)}")
    return rows, violations


def documents(corpus_db: Path) -> dict[str, dict[str, Any]]:
    with sqlite3.connect(f"file:{corpus_db}?mode=ro", uri=True) as con:
        con.row_factory = sqlite3.Row
        return {r["doc_id"]: dict(r) for r in con.execute("SELECT * FROM documents")}


def distractors(docs: Mapping[str, Mapping[str, Any]], as_of: str) -> dict[str, int]:
    """How many indexed documents each KR-04 filter has to keep out (proof the filter was exercised)."""
    probe = {"filters": {"as_of": as_of, "home_state": "IN-MH", "lender_type": "commercial_bank"}}
    out: dict[str, int] = {}
    for doc in docs.values():
        if (why := kr04_violation(doc, probe, docs)) and why != "other_case":
            out[why] = out.get(why, 0) + 1
    out["case_scoped_kfs"] = sum(1 for d in docs.values() if d["case_id"])
    return out


def report(
    rows: list[Row],
    violations: list[str],
    queries: list[dict[str, Any]],
    docs: Mapping[str, Mapping[str, Any]],
    awaiting: list[str],
    meta: Mapping[str, Any],
    rerank_note: str,
) -> str:
    n = len(queries)
    answerable = {q["id"] for q in queries if set(q["relevant_doc_ids"]) & docs.keys()}
    real = sum(1 for d in docs.values() if d["legal_basis"] != "L5")
    best = max(rows, key=lambda r: (len(r.hits5), len(r.hits10)))
    lines = [
        f"# Retrieval evaluation — {meta['date']}",
        "",
        "KR-01..05 · ADR 0013 (reranker) · ADR 0019 (KR-04 filters). Generated by `make retrieval-eval`.",
        "",
        "## Run record (#13)",
        "",
        *(f"- **{k}:** {v}" for k, v in meta.items()),
        f"- **Indexed documents:** {len(docs)} ({real} real, {len(docs) - real} synthetic)",
        f"- **Queries:** {n}; answerable now (a labelled document is indexed): {len(answerable)}",
        "",
        "## Headline (KR-05)",
        "",
        f"Best configuration: **{best.strategy} / {best.mode} / rerank {'on' if best.rerank else 'off'}**"
        f" — a relevant passage in the top 5 for **{len(best.hits5)}/{n}** queries"
        f" ({len(best.hits5 & answerable)}/{len(answerable)} answerable). Target ≥{TARGET}/40:"
        f" **{'MET' if len(best.hits5) >= TARGET else 'OPEN'}**.",
        "",
        "## recall@k (queries with a relevant passage in the top k)",
        "",
        rerank_note,
        "",
        "| Chunking | Retriever | Rerank | recall@5 | recall@10 | doc-level recall@5 | answerable @5 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.strategy} | {r.mode} | {'on' if r.rerank else 'off'} | {len(r.hits5)}/{n} "
            f"| {len(r.hits10)}/{n} | {len(r.doc_hits5)}/{n} | {len(r.hits5 & answerable)}/{len(answerable)} |"
        )
    missed = sorted({q["id"] for q in queries} - best.hits5)
    lines += [
        "",
        f"Missed by the best configuration: {', '.join(missed) or 'none'}.",
        "",
        "## KR-04: nothing superseded, out of state, for another lender type or another case",
        "",
        "Indexed documents each filter must keep out: "
        + ", ".join(f"{k} {v}" for k, v in sorted(distractors(docs, meta["as_of"]).items()))
        + ".",
        "",
        f"Passages checked: every top-10 result of every configuration. Violations: **{len(violations)}**.",
        *(f"- {v}" for v in violations[:50]),
        "",
        "## Items awaiting corpus documents",
        "",
        *(f"- {a}" for a in awaiting),
        *([] if awaiting else ["None."]),
        "",
    ]
    return "\n".join(lines)


def main(env: Mapping[str, str] = os.environ) -> int:
    from credassure.retrieval.cli import embed_target, embedder, endpoint, paths
    from credassure.retrieval.index import open_chroma
    from credassure.retrieval.search import RERANKER_REVISION, make_reranker

    corpus_db, _, chroma_path = paths(env)
    queries = load_queries()
    docs = documents(corpus_db)
    reranker, note = None, "Rerank on: not run."
    try:
        reranker = make_reranker(
            "local_cross_encoder", env.get("RERANKER_MODEL", "BAAI/bge-reranker-base")
        )
        note = (
            "Rerank on: local cross-encoder over the top 30 (mentor-approved 2026-11-14, ADR 0013)."
        )
    except ImportError:
        note = "Rerank on: not run — install the `rerank` extra (ADR 0013)."
    searcher = Searcher(corpus_db, open_chroma(chroma_path), embedder(env), reranker=reranker)
    rows, violations = evaluate(
        searcher,
        queries,
        docs,
        rerank_options=(False, True) if reranker else (False,),
        progress=lambda line: print(line, file=sys.stderr, flush=True),
    )
    refs = check()
    awaiting = [a for a in refs.awaiting if a.split(":")[0].startswith("Q")]
    today = datetime.now(UTC).date().isoformat()
    url, model = embed_target(env)
    meta = {
        "date": today,
        "as_of": queries[0]["filters"]["as_of"],
        "embedding model": f"{model} at {endpoint(url)}",
        "reranker": (
            f"{env.get('RERANKER_MODEL', 'BAAI/bge-reranker-base')}@"
            f"{env.get('RERANKER_REVISION', RERANKER_REVISION)[:12]}"
            if reranker
            else "none"
        ),
        "depth": "top 30 per retriever, RRF k=60, top 10 kept",
        "corpus db": str(corpus_db),
    }
    out = REPO / "evaluation" / "reports" / f"retrieval-{today}.md"
    out.write_text(report(rows, violations, queries, docs, awaiting, meta, note), encoding="utf-8")
    print(f"retrieval-eval: wrote {out.relative_to(REPO)}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
