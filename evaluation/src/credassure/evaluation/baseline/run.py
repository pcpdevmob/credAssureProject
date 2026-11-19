"""``make baseline``: run S1-S3 over the 100 items, score, and write results, summary and run record.

Writes evaluation/baseline/results/<strategy>.jsonl, summary.md and record_<strategy>.json. Exits early, without
writing results, when the endpoint does not answer.
"""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..check_corpus_refs import known_doc_ids
from ..gold.data import REPO
from ..record import run_record
from ..scorers import BRD_CLASS, score
from .client import Chat, InfraError, OpenAICompatible
from .strategies import PROMPTS, run

RESULTS = REPO / "evaluation" / "baseline" / "results"
ITEMS = REPO / "evaluation" / "testset" / "v1" / "items.jsonl"


def evaluate(
    strategy: str, items: list[dict[str, Any]], chat: Chat, out: Path
) -> list[dict[str, Any]]:
    known = known_doc_ids()
    record = run_record(chat.model, chat.endpoint, PROMPTS, len(items), strategy)
    meta = {k: record[k] for k in ("endpoint", "context_length", "run_kind")}
    results = []
    for item in items:
        try:
            answer, tokens, raw = run(strategy, item, chat)
        except InfraError as exc:  # endpoint failed twice: not the model's answer, so not scored
            results.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "passed": None,
                    "failure_class": "infra_error",
                    "detail": str(exc),
                    "tokens": 0,
                    "answer": None,
                    "raw_tail": "",
                    **meta,
                }
            )
            continue
        verdict = score(item, answer, known)
        results.append(
            {
                "id": item["id"],
                "category": item["category"],
                "passed": verdict["passed"],
                "failure_class": verdict["failure_class"],
                "detail": verdict["detail"],
                "tokens": tokens,
                "answer": answer,
                "raw_tail": raw[-400:],
                **meta,
            }
        )
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{strategy}.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in results),
        encoding="utf-8",
    )
    (out / f"record_{strategy}.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return results


def _scored(rs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rs if r["failure_class"] != "infra_error"]


def _cell(rs: list[dict[str, Any]]) -> str:
    scored = _scored(rs)
    infra = len(rs) - len(scored)
    return f"{sum(bool(r['passed']) for r in scored)}/{len(scored)}" + (
        f" ({infra} infra)" if infra else ""
    )


def summary(by_strategy: dict[str, list[dict[str, Any]]], record: dict[str, Any]) -> str:
    """Accuracy is passed / scored items; infra_error items (endpoint failed twice) are excluded and counted."""
    first = next(iter(by_strategy.values()))
    categories = list(dict.fromkeys(r["category"] for rs in by_strategy.values() for r in rs))
    kind = record["run_kind"]
    lines = [
        "# Baseline results (BRD §12)",
        "",
        f"Run kind: **{kind}**"
        + {
            "graded": "",
            "local_provisional": " (local Ollama: the evaluated path, ADR 0036)",
            "smoke_test": " (smoke test: context length not set, not a reported result)",
        }.get(kind, "")
        + f" · endpoint `{record['endpoint']}` · model `{record['model']}`"
        + f" · context length {record['context_length'] or 'not set (Ollama default)'}",
        "",
        "Cells are passed/scored; items whose call failed twice are excluded and shown as infra.",
        "",
        "| Category | Items | " + " | ".join(s.upper() for s in by_strategy) + " |",
        "|" + "---|" * (len(by_strategy) + 2),
    ]
    for cat in categories:
        cells = [_cell([r for r in rs if r["category"] == cat]) for rs in by_strategy.values()]
        count = sum(1 for r in first if r["category"] == cat)
        lines.append(f"| {cat} | {count} | " + " | ".join(cells) + " |")
    lines += [
        f"| **Total** | {len(first)} | "
        + " | ".join(f"**{_cell(rs)}**" for rs in by_strategy.values())
        + " |",
        "| infra_error | | "
        + " | ".join(str(len(rs) - len(_scored(rs))) for rs in by_strategy.values())
        + " |",
        "",
        "## Failure classes",
        "",
    ]
    for name, rs in by_strategy.items():
        brd = Counter(
            BRD_CLASS.get(r["failure_class"], "tool_error") for r in _scored(rs) if not r["passed"]
        )
        lines.append(
            f"- **{name.upper()}** (BRD §13 classes): "
            + (", ".join(f"{k} {v}" for k, v in brd.most_common()) or "none")
        )
    lines.append("")
    for name, rs in by_strategy.items():
        counts = Counter(r["failure_class"] for r in rs if not r["passed"])
        lines.append(
            f"- **{name.upper()}**: "
            + (", ".join(f"{k} {v}" for k, v in counts.most_common()) or "none")
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m credassure.evaluation.baseline.run")
    parser.add_argument("--strategy", choices=["s1", "s2", "s3", "all"], default="all")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)
    chat = OpenAICompatible()
    if not chat.available():
        print(
            f"Endpoint {chat.endpoint} is not answering; start Ollama (ADR 0017) or set EVAL_BASE_URL."
        )
        return 1
    items = [json.loads(line) for line in ITEMS.read_text(encoding="utf-8").splitlines()]
    items = items[: args.limit] if args.limit else items
    strategies = ["s1", "s2", "s3"] if args.strategy == "all" else [args.strategy]
    by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for strategy in strategies:
        by_strategy[strategy] = evaluate(strategy, items, chat, RESULTS)
        print(f"{strategy}: {_cell(by_strategy[strategy])}")
    record = run_record(chat.model, chat.endpoint, PROMPTS, len(items), "summary")
    (RESULTS / "summary.md").write_text(summary(by_strategy, record), encoding="utf-8")
    print((RESULTS / "summary.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
