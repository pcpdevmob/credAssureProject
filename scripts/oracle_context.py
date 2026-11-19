"""Oracle-context run for the regulatory items: how many would the copilot get right if search were
perfect? (course template §7 "oracle-context baseline": separates retrieval error from model error)

For each answerable regulatory item of the frozen set (read only; this is a reported comparison,
never used to tune anything), the copilot's search tools return the gold passages instead of the
search results: the chunks of the gold documents that contain the gold evidence quote, topped up to
five with the reranker's best other chunks of those documents. Everything else is the real turn: the
same answer prompt, span citations, the real Critic and the frozen strict scorer. Cache off.

    uv run --env-file .env --env-file deploy/env/models-local.env python scripts/oracle_context.py

Prints a table and writes var/oracle-context.jsonl. Writes nothing to any database you use.
"""

import argparse
import dataclasses
import json
import re
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from credassure.agents.copilot import agent as copilot
from credassure.evaluation.check_corpus_refs import known_doc_ids
from credassure.evaluation.scorers import score
from credassure.gateway.main import _default_llm, _searcher, create_app
from credassure.gateway.settings import Settings
from credassure.retrieval.search import Passage

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "evaluation" / "testset" / "v1" / "items.jsonl"
SEARCH_TOOLS = ("search_regulations", "search_policies")
K = 5


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9₹]+", " ", text.lower()).strip()


def _gold_passages(
    db: Path, item: Mapping[str, Any], strategy: str, rerank: Any
) -> tuple[list[dict[str, Any]], int]:
    """Gold-document chunks: those holding an evidence quote first, then the reranker's best."""
    gold = item["gold"]
    docs = list(gold.get("relevant_doc_ids") or [])
    quotes = [_norm(e["quote"]) for e in gold.get("evidence") or [] if e.get("quote")]
    con = sqlite3.connect(db)
    rows = []
    for doc in docs:  # one bound query per gold document; no SQL is built from data
        rows += con.execute(
            "SELECT c.chunk_id, c.doc_id, d.title, d.collection, c.section_path,"
            " d.effective_from, c.text, c.injection_flag FROM chunks c JOIN documents d"
            " USING (doc_id) WHERE c.strategy = ? AND c.doc_id = ? ORDER BY c.ordinal",
            (strategy, doc),
        ).fetchall()
    con.close()
    passages = [
        Passage(r[0], r[1], r[2], r[3], r[4], None, r[6], bool(r[7])) for r in rows
    ]  # effective_from left None: the gold documents are in force by construction
    with_quote = [p for p in passages if any(q and q in _norm(p.text) for q in quotes)]
    rest = [p for p in passages if p not in with_quote]
    if rest and rerank is not None:
        scores = rerank(item["input"]["question"], [p.text for p in rest])
        rest = [p for _, p in sorted(zip(scores, rest, strict=True), key=lambda x: -x[0])]
    chosen = (with_quote + rest)[:K]
    return [dataclasses.asdict(p) for p in chosen], len(with_quote)


class Oracle:
    """ToolPort wrapper: search tools answer with the gold passages; every other call is real."""

    def __init__(self, inner: Any, passages: list[dict[str, Any]]) -> None:
        self.inner, self.passages = inner, passages

    def call(self, name: str, case_id: str, args: Any = None) -> Any:
        if name in SEARCH_TOOLS:
            return list(self.passages)
        return (
            self.inner.call(name, case_id, args)
            if args is not None
            else self.inner.call(name, case_id)
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ids", nargs="*", default=None)
    args = ap.parse_args()
    settings = Settings(
        case_db=ROOT / "var" / "oracle-case.db", tenant_id="default", llm_cache_path=None
    )
    llm = _default_llm(settings)
    if llm is None:
        raise SystemExit("needs LLM_ENABLED=true and a reachable model")
    app = create_app(settings, llm=llm)
    rerank = _searcher(settings)().reranker
    known = known_doc_ids()
    items = [json.loads(x) for x in ITEMS.open()]
    items = [
        i
        for i in items
        if i["category"] == "regulatory"
        and i.get("subtype") != "abstention"
        and (not args.ids or i["id"] in args.ids)
    ]
    out = ROOT / "var" / "oracle-context.jsonl"
    rows = []
    with out.open("w") as f:
        for it in items:
            passages, quoted = _gold_passages(settings.corpus_db, it, "section", rerank)
            tools = Oracle(app.state.services.copilot_tools(), passages)
            rep = copilot.answer(
                it["input"]["question"], case_id=None, tools=tools, llm=llm, history=(),
                offer_ids=(), as_of=settings.as_of_date,
            )  # fmt: skip
            cited = sorted({str(c["chunk_id"]).split("#")[0] for c in rep.citations})
            answer = {"answer": rep.answer, "citations": cited, "refused": rep.refused}
            res = score(dict(it), answer, known)
            row = {
                "id": it["id"], "passed": bool(res["passed"]), "detail": res.get("detail"),
                "gold_passages": len(passages), "with_quote": quoted, "abstained": rep.abstained,
                "findings": list(rep.findings), "cited": cited, "answer": rep.answer[:300],
            }  # fmt: skip
            rows.append(row)
            f.write(json.dumps(row) + "\n")
            print(f"{row['id']} {'PASS' if row['passed'] else 'FAIL'} quote_chunks={quoted} "
                  f"cited={cited} {row['detail'] or ''}", flush=True)  # fmt: skip
    n, ok = len(rows), sum(r["passed"] for r in rows)
    abst = sum(r["abstained"] for r in rows)
    noq = sum(1 for r in rows if not r["with_quote"])
    print(f"\nOracle context: {ok}/{n} answerable regulatory items pass ({abst} abstained; "
          f"{noq} with no chunk holding the gold quote)")  # fmt: skip
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
