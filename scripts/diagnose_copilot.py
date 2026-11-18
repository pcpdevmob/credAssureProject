"""Why does the copilot abstain on a regulatory item? (G4 diagnosis, 2026-11-18 live run: 9/25.)

For each regulatory item of the frozen set (read only, never tuned on), without changing anything:
  1. retrieval, no model: the hybrid top 5, whether a gold document is among them, and the
     reranker's best score against ANSWERABILITY_THRESHOLD (below it the copilot abstains);
  2. with --answer, the full copilot turn on the configured model, outside a case: the route, the
     tool, and what removed the answer (passages dropped, sentences cut, Critic finding codes).

    uv run --env-file .env --env-file deploy/env/models-local.env python scripts/diagnose_copilot.py
    ... python scripts/diagnose_copilot.py --answer --ids T001 T002

Writes nothing to any database; prints a table and writes var/diagnose-copilot.jsonl.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from credassure.agents.copilot import agent as copilot
from credassure.agents.copilot.intent import route
from credassure.gateway.main import _default_llm, _searcher, create_app
from credassure.gateway.settings import Settings
from credassure.retrieval.search import Filters

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "evaluation" / "testset" / "v1" / "items.jsonl"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--answer", action="store_true", help="also run the copilot on the model")
    ap.add_argument("--ids", nargs="*", default=None)
    args = ap.parse_args()

    settings = Settings(case_db=ROOT / "var" / "diagnose-case.db", tenant_id="default")
    searcher = _searcher(settings)()
    gate = settings.answerability_threshold
    filters = Filters(as_of=settings.as_of_date, home_state=settings.home_state)
    items = [json.loads(x) for x in ITEMS.open()]
    items = [
        i
        for i in items
        if i["category"] == "regulatory"
        and i.get("subtype") != "abstention"
        and (not args.ids or i["id"] in args.ids)
    ]
    llm = _default_llm(settings) if args.answer else None
    if args.answer and llm is None:
        sys.exit("--answer needs LLM_ENABLED=true and a reachable model")
    tools = None
    if args.answer:
        tools = create_app(settings, llm=llm).state.services.copilot_tools()

    out = ROOT / "var" / "diagnose-copilot.jsonl"
    print(f"reranker={settings.reranker} gate={gate} rewrite={settings.retrieval_query_rewrite}")
    print(f"{'id':5} {'gold@5':6} {'top':>6} {'gate':5} {'route':10} answer")
    with out.open("w") as f:
        for it in items:
            q = it["input"]["question"]
            gold = set(it["gold"].get("relevant_doc_ids") or [])
            scored = searcher.scored(q, filters=filters, k=30)
            scores = [s for _, s in scored if s is not None]
            top = max(scores) if scores else None
            docs = [p.doc_id for p, _ in scored[:5]]
            row: dict[str, Any] = {
                "id": it["id"],
                "gold_in_top5": bool(gold & set(docs)),
                "top5": docs,
                "top_score": top,
                "gate_passes": gate is None or top is None or top >= gate,
                "route": (r.intent if (r := route(q, has_case=True)) else "model"),
            }
            if tools is not None:
                rep = copilot.answer(
                    q,
                    case_id=None,
                    tools=tools,
                    llm=llm,
                    history=(),
                    offer_ids=(),
                    as_of=settings.as_of_date,
                )
                row |= {
                    "abstained": rep.abstained,
                    "tool": rep.tool,
                    "dropped": rep.dropped,
                    "cut": rep.cut,
                    "findings": list(rep.findings),
                    "answer": rep.answer[:300],
                }
            f.write(json.dumps(row) + "\n")
            ans = ""
            if "abstained" in row:
                ans = "ABSTAIN " + ",".join(row["findings"]) if row["abstained"] else "answered"
                ans += f" cut={row['cut']} dropped={row['dropped']}"
            top_s = f"{top:.3f}" if top is not None else "-"
            print(
                f"{row['id']:5} {row['gold_in_top5']!s:6} {top_s:>6}"
                f" {row['gate_passes']!s:5} {row['route']:10} {ans}"
            )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
