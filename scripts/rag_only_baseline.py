"""RAG-only baseline for the regulatory items: prompting + retrieval, no agents (course template,
"prompting + RAG" row of the small-model compensation table).

Sits between the closed-book baselines (S1-S3, no documents) and the full system. For each of the
25 regulatory items of the frozen set (read only; a reported comparison, never used to tune
anything) the question goes through the same hybrid search the copilot uses (BM25 + dense, RRF,
context headers, glossary rewrite, reranker scores, top 5 from the public collection), and the five
passages are pasted into the S1 baseline prompt (same system prompt, same examples, same answer
schema). One model call per item. Nothing else of the system runs: no copilot routing, no injection
filter on passages, no span numbering or sentence cutting, no Critic, no ledger, and by default no
answerability gate (pass --with-gate to keep it). The answer is scored by the frozen strict scorer.
Cache off: every call is fresh.

    make rag-baseline        (= uv run <env files> python scripts/rag_only_baseline.py)

Prints a table and writes var/rag-only-baseline.jsonl and var/rag-only-baseline.record.json.
Writes nothing to any database you use.
"""

import argparse
import datetime
import json
import tempfile
from pathlib import Path
from typing import Any

from credassure.evaluation.baseline import client as baseline_client
from credassure.evaluation.baseline.client import InfraError, OpenAICompatible
from credassure.evaluation.baseline.strategies import PROMPTS, S1_EXAMPLES, SYSTEM, parse_json
from credassure.evaluation.check_corpus_refs import known_doc_ids
from credassure.evaluation.record import run_record
from credassure.evaluation.scorers import score
from credassure.gateway.main import create_app
from credassure.gateway.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "evaluation" / "testset" / "v1" / "items.jsonl"
TASK = "Answer the question from the passages below and cite the source documents by doc_id."
MAX_PASSAGE_CHARS = 2_500  # five passages stay well inside the 8k-token window


def _material(passages: list[dict[str, Any]]) -> str:
    if not passages:
        return "(no passages found)"
    return "\n\n".join(
        f"## doc_id: {p['doc_id']} | {p.get('title') or ''} | {p.get('section_path') or ''}\n"
        f"{str(p['text'])[:MAX_PASSAGE_CHARS]}"
        for p in passages
    )


def user_prompt(item: dict[str, Any], passages: list[dict[str, Any]]) -> str:
    """The S1 user prompt with the retrieved passages as the material."""
    inp = item["input"]
    return (
        f"Task: {TASK}\nCase: {inp.get('case_id', '-')}  Actor: {inp.get('actor', '-')}"
        f"\nUser: {inp['question']}\n"
        f"Answer JSON schema: {item['answer_schema']}\n\nMaterial:\n{_material(passages)}"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ids", nargs="*", default=None)
    ap.add_argument("--with-gate", action="store_true", help="keep the answerability gate")
    args = ap.parse_args()
    overrides: dict[str, Any] = {} if args.with_gate else {"answerability_threshold": None}
    settings = Settings(
        case_db=ROOT / "var" / "rag-only-case.db",
        tenant_id="default",
        llm_cache_path=None,
        **overrides,
    )
    tools = create_app(settings, llm=None).state.services.copilot_tools()
    chat = OpenAICompatible()
    if not chat.available():
        raise SystemExit(f"model endpoint {chat.endpoint} not reachable")
    baseline_client.CACHE = Path(tempfile.mkdtemp(prefix="rag-only-"))  # cache off: fresh calls

    known = known_doc_ids()
    items = [json.loads(x) for x in ITEMS.open()]
    items = [
        i for i in items if i["category"] == "regulatory" and (not args.ids or i["id"] in args.ids)
    ]
    record = run_record(chat.model, chat.endpoint, PROMPTS, len(items), "rag_only_s1")
    record |= {
        "retrieval": {
            "tool": "search_regulations",
            "k": 5,
            "search_mode": settings.copilot_search_mode,
            "reranker": settings.reranker,
            "query_rewrite": settings.retrieval_query_rewrite,
            "rerank_order": settings.rerank_order,
            "answerability_threshold": settings.answerability_threshold,
        }
    }
    out = ROOT / "var" / "rag-only-baseline.jsonl"
    rows = []
    with out.open("w") as f:
        for it in items:
            question = it["input"]["question"]
            passages = tools.call("search_regulations", "", {"query": question[:600]})
            retrieved = sorted({str(p["doc_id"]) for p in passages})
            relevant = set(it["gold"].get("relevant_doc_ids") or [])
            messages = [
                {"role": "system", "content": f"{SYSTEM}\n{S1_EXAMPLES}"},
                {"role": "user", "content": user_prompt(it, passages)},
            ]
            try:
                text, tokens = chat.complete(messages, 0.0, 1)
            except InfraError as exc:
                row = {"id": it["id"], "passed": None, "failure_class": "infra_error",
                       "detail": str(exc)}  # fmt: skip
            else:
                answer = parse_json(text)
                res = score(it, answer, known)
                row = {
                    "id": it["id"],
                    "subtype": it.get("subtype") or "answerable",
                    "passed": bool(res["passed"]),
                    "failure_class": res.get("failure_class"),
                    "detail": res.get("detail"),
                    "passages": len(passages),
                    "retrieved_docs": retrieved,
                    "gold_retrieved": bool(relevant & set(retrieved)),
                    "cited": sorted((answer or {}).get("citations") or []),
                    "tokens": tokens,
                    "answer": str((answer or {}).get("answer", ""))[:300],
                    "raw_tail": text[-400:],
                }
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{row['id']} {'PASS' if row['passed'] else 'FAIL'} "
                  f"gold_in_top5={row.get('gold_retrieved')} cited={row.get('cited')} "
                  f"{row.get('detail') or ''}", flush=True)  # fmt: skip
    record["utc_finished"] = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    (ROOT / "var" / "rag-only-baseline.record.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    def _count(sub: str | None) -> tuple[int, int]:
        rs = [r for r in rows if sub is None or r.get("subtype") == sub]
        return sum(bool(r["passed"]) for r in rs), len(rs)

    ok, n = _count(None)
    ans_ok, ans_n = _count("answerable")
    abs_ok, abs_n = _count("abstention")
    hit = sum(1 for r in rows if r.get("subtype") == "answerable" and r.get("gold_retrieved"))
    infra = sum(1 for r in rows if r.get("failure_class") == "infra_error")
    print(
        f"\nRAG-only (S1 + hybrid top-5, no agents): {ok}/{n} regulatory; answerable "
        f"{ans_ok}/{ans_n} (gold doc in top 5 for {hit}/{ans_n}); abstention {abs_ok}/{abs_n}; "
        f"infra errors {infra}"
    )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
