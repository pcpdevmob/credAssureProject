"""Does SOURCE_PRIORITY help the copilot cite the right document? (retrieval DEV split only)

The 20 dev queries (evaluation/retrieval/dev/queries.jsonl, never the frozen 40 or the 100-item set)
go through the full copilot turn, outside a case, on the configured model, once with the setting off
and once on. Same scorer shape as the frozen strict scorer: an answer passes when it cites at least
one labelled relevant document. The model response cache is off, so every answer is fresh.

    uv run --env-file .env --env-file deploy/env/models-local.env \
        python scripts/copilot_dev_citations.py            # about 30 minutes on qwen3:8b

Prints a table and writes var/copilot-dev-citations.jsonl. Writes nothing to any database you use.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from credassure.agents.copilot import agent as copilot
from credassure.gateway.main import _default_llm, create_app
from credassure.gateway.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "evaluation" / "retrieval" / "dev" / "queries.jsonl"


def _run(priority: bool, rows: list[dict[str, Any]], db: Path) -> list[dict[str, Any]]:
    settings = Settings(
        case_db=db, tenant_id="default", source_priority=priority, llm_cache_path=None
    )
    llm = _default_llm(settings)
    if llm is None:
        raise SystemExit("needs LLM_ENABLED=true and a reachable model")
    tools = create_app(settings, llm=llm).state.services.copilot_tools()
    out = []
    for r in rows:
        rep = copilot.answer(
            r["query"], case_id=None, tools=tools, llm=llm, history=(), offer_ids=(),
            as_of=settings.as_of_date,
        )  # fmt: skip
        cited = sorted({str(c["chunk_id"]).split("#")[0] for c in rep.citations})
        hit = bool(set(cited) & set(r["relevant_doc_ids"]))
        out.append(
            {"id": r["id"], "priority": priority, "pass": hit, "abstained": rep.abstained,
             "cited": cited, "relevant": r["relevant_doc_ids"], "answer": rep.answer[:300]}
        )  # fmt: skip
        print(f"{r['id']} priority={'on ' if priority else 'off'} "
              f"{'PASS' if hit else 'FAIL'} cited={cited}", flush=True)  # fmt: skip
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ids", nargs="*", default=None)
    args = ap.parse_args()
    rows = [json.loads(x) for x in DEV.open()]
    rows = [r for r in rows if not args.ids or r["id"] in args.ids]
    db = ROOT / "var" / "copilot-dev-case.db"
    off, on = _run(False, rows, db), _run(True, rows, db)
    out = ROOT / "var" / "copilot-dev-citations.jsonl"
    with out.open("w") as f:
        for row in off + on:
            f.write(json.dumps(row) + "\n")
    print("\nid    off   on")
    for a, b in zip(off, on, strict=True):
        flag = "" if a["pass"] == b["pass"] else ("  gained" if b["pass"] else "  LOST")
        was, now = ("PASS" if x["pass"] else "fail" for x in (a, b))
        print(f"{a['id']:5} {was:5} {now:5}{flag}")
    n = len(rows)
    print(f"\nSOURCE_PRIORITY=false: {sum(r['pass'] for r in off)}/{n} cite a relevant document "
          f"({sum(r['abstained'] for r in off)} abstained)")  # fmt: skip
    print(f"SOURCE_PRIORITY=true:  {sum(r['pass'] for r in on)}/{n} cite a relevant document "
          f"({sum(r['abstained'] for r in on)} abstained)")  # fmt: skip
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
