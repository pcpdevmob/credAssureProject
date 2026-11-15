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
from collections.abc import Callable, Iterable, Mapping, Sequence
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
ISOLATION = REPO / "evaluation" / "retrieval" / "v1" / "isolation.jsonl"  # case-tied, not KR-05
TARGET = 34
LABEL_SETS = {  # same 40 queries, wider labels (judging/README.md); v1.0 stays the headline
    "v1.0": QUERIES,
    "v1.1-silver strict": QUERIES.with_name("queries.v1.1-silver.jsonl"),
    "v1.1-silver lenient": QUERIES.with_name("queries.v1.1-silver-lenient.jsonl"),
}


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


def label_match(path: str | None, label: Mapping[str, Any]) -> bool:
    """`exact` (silver labels on a passage before any heading) matches only unsectioned passages, so
    one judged preamble does not label every section of its document."""
    if label.get("exact"):
        return _ws(path or "") == _ws(label["section_path"])
    return section_match(path, label["section_path"])


def is_relevant(p: Passage, q: Mapping[str, Any], *, section: bool) -> bool:
    if not section or not q.get("relevant_sections"):
        return p.doc_id in q["relevant_doc_ids"]
    return any(
        p.doc_id == s["doc_id"] and label_match(p.section_path, s) for s in q["relevant_sections"]
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


Config = tuple[str, str, bool]  # (chunking, retriever, rerank)
Hits = dict[Config, dict[str, list[Passage]]]


def run_searches(
    searcher: Searcher,
    queries: list[dict[str, Any]],
    *,
    rerank_options: Iterable[bool] = (False,),
    progress: Callable[[str], None] | None = None,
) -> Hits:
    """One search pass (top 10) per configuration and query; scoring, isolation and the judging pool
    all read it, so they see exactly the same results."""
    hits: Hits = {}
    for strategy in STRATEGIES:
        for mode in MODES:
            for rerank in rerank_options:
                hits[(strategy, mode, rerank)] = {
                    q["id"]: searcher.search_knowledge(
                        q["query"],
                        case_id=q["filters"].get("case_id"),
                        tenant_id=q["filters"].get("tenant_id"),
                        filters=filters_for(q),
                        strategy=strategy,
                        mode=mode,  # type: ignore[arg-type]
                        k=10,
                        rerank=rerank,
                    )
                    for q in queries
                }
                if progress:
                    progress(f"{strategy}/{mode}/rerank={rerank}: searched")
    return hits


def score(
    hits: Hits, queries: list[dict[str, Any]], docs: Mapping[str, Mapping[str, Any]]
) -> tuple[list[Row], list[str]]:
    rows, violations = [], []
    for (strategy, mode, rerank), by_q in hits.items():
        row = Row(strategy, mode, rerank)
        for q in queries:
            found = by_q[q["id"]]
            if any(is_relevant(p, q, section=True) for p in found[:5]):
                row.hits5.add(q["id"])
            if any(is_relevant(p, q, section=True) for p in found):
                row.hits10.add(q["id"])
            if any(is_relevant(p, q, section=False) for p in found[:5]):
                row.doc_hits5.add(q["id"])
            for p in found:
                if why := kr04_violation(docs[p.doc_id], q, docs):
                    violations.append(f"{q['id']} {strategy}/{mode}: {p.doc_id} ({why})")
        rows.append(row)
    return rows, violations


def isolation(
    hits: Hits, checks: list[dict[str, Any]], docs: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    """SUP-08 / BR-14 live: in every configuration a case-tied query returns its own case's KFS in
    the top 10 and no passage that fails KR-04 for it (another case's KFS above all)."""
    fails = []
    for (strategy, mode, rerank), by_q in hits.items():
        cfg = f"{strategy}/{mode}/rerank={'on' if rerank else 'off'}"
        for c in checks:
            f, found = c["filters"], by_q[c["id"]]
            own = (f["case_id"], f.get("tenant_id"))
            if not any(
                (docs[p.doc_id]["case_id"], docs[p.doc_id]["tenant_id"]) == own for p in found
            ):
                fails.append(f"{c['id']} {cfg}: no {f['case_id']} KFS in the top 10")
            fails += [
                f"{c['id']} {cfg}: {p.doc_id} ({why})"
                for p in found
                if (why := kr04_violation(docs[p.doc_id], c, docs))
            ]
    return fails


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
    checks: Sequence[Mapping[str, Any]] = (),
    isolation_fails: Sequence[str] = (),
) -> str:
    n = len(queries)
    answerable = {q["id"] for q in queries if set(q["relevant_doc_ids"]) & docs.keys()}
    real = sum(1 for d in docs.values() if d["legal_basis"] != "L5")
    best = max(rows, key=lambda r: (len(r.hits5), len(r.hits10)))
    kfs = [d for d in docs.values() if d["case_id"]]
    kfs_in_force = sum(
        1 for d in kfs if d["effective_from"] and d["effective_from"] <= meta["as_of"]
    )
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
        f"Case-scoped KFS in force on {meta['as_of']} (else the date filter hides them before the"
        f" case filter is reached): {kfs_in_force}/{len(kfs)}.",
        "",
        f"Passages checked: every top-10 result of every configuration. Violations: **{len(violations)}**.",
        *(f"- {v}" for v in violations[:50]),
        "",
        "## Live case isolation (SUP-08, BR-14)",
        "",
        "Case-tied checks, separate from the 40 KR-05 queries. Each must return its own case's KFS in"
        f" the top 10 and nothing that fails KR-04 (another case's KFS above all), in all {len(rows)}"
        " configurations.",
        "",
        "| Check | Case | Query | Result |",
        "|---|---|---|---|",
        *(
            f"| {c['id']} | {c['filters']['case_id']} | {c['query']} | "
            f"{'FAIL' if any(x.startswith(c['id'] + ' ') for x in isolation_fails) else 'PASS'} |"
            for c in checks
        ),
        "",
        f"Failures: **{len(isolation_fails)}**." if checks else "Not run (no isolation checks).",
        *(f"- {x}" for x in isolation_fails[:50]),
        "",
        "## Items awaiting corpus documents",
        "",
        *(f"- {a}" for a in awaiting),
        *([] if awaiting else ["None."]),
        "",
    ]
    return "\n".join(lines)


def label_sets_section(
    hits: Hits, docs: Mapping[str, Mapping[str, Any]], sets: Mapping[str, Path] = LABEL_SETS
) -> str:
    """recall@5 / @10 per configuration under each label set that exists, from the same search pass."""
    scored = {
        name: score(hits, load_queries(path), docs)[0]
        for name, path in sets.items()
        if path.exists()
    }
    n = len(load_queries(QUERIES))
    names = list(scored)
    lines = [
        "## recall@k under label sets v1.0 and v1.1-silver",
        "",
        "Same search results, scored three ways. v1.1-silver = v1.0 plus pool items a blind LLM judge"
        " graded 2 (strict) or ≥ 1 (lenient); **LLM-judged, human agreement pending**"
        " (`evaluation/retrieval/v1/judging/labels_v1.1-silver_diff.md`).",
        "",
        "| Chunking | Retriever | Rerank | "
        + " | ".join(f"{x} @5 | {x} @10" for x in names)
        + " |",
        "|---|---|---|" + "---|---|" * len(names),
    ]
    for i, r in enumerate(scored[names[0]]):
        cells = " | ".join(
            f"{len(scored[x][i].hits5)}/{n} | {len(scored[x][i].hits10)}/{n}" for x in names
        )
        lines.append(f"| {r.strategy} | {r.mode} | {'on' if r.rerank else 'off'} | {cells} |")
    lines.append("")
    for x in names:
        best = max(scored[x], key=lambda r: (len(r.hits5), len(r.hits10)))
        lines.append(
            f"- **{x}:** best {best.strategy}/{best.mode}/rerank {'on' if best.rerank else 'off'}"
            f" {len(best.hits5)}/{n} @5 (target ≥{TARGET}: {'MET' if len(best.hits5) >= TARGET else 'OPEN'})"
        )
    return "\n".join([*lines, ""])


def open_searcher(env: Mapping[str, str]) -> tuple[Searcher, Path, bool, str]:
    """The live index with the pinned cross-encoder when the `rerank` extra is installed (ADR 0013)."""
    from credassure.retrieval.cli import embedder, paths
    from credassure.retrieval.index import open_chroma
    from credassure.retrieval.search import make_reranker

    corpus_db, _, chroma_path = paths(env)
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
    return searcher, corpus_db, reranker is not None, note


def main(env: Mapping[str, str] = os.environ) -> int:
    from credassure.retrieval.cli import embed_target, endpoint
    from credassure.retrieval.search import RERANKER_REVISION

    searcher, corpus_db, reranker, note = open_searcher(env)
    queries = load_queries()
    checks = load_queries(ISOLATION)
    docs = documents(corpus_db)
    hits = run_searches(
        searcher,
        queries + checks,
        rerank_options=(False, True) if reranker else (False,),
        progress=lambda line: print(line, file=sys.stderr, flush=True),
    )
    rows, violations = score(hits, queries, docs)
    isolation_fails = isolation(hits, checks, docs)
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
    text = report(rows, violations, queries, docs, awaiting, meta, note, checks, isolation_fails)
    text += "\n" + label_sets_section(hits, docs)
    out.write_text(text, encoding="utf-8")
    print(f"retrieval-eval: wrote {out.relative_to(REPO)}")
    return 1 if violations or isolation_fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
