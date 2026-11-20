"""Compare two evaluation runs item by item (course endpoint vs local model, or any two runs).

    make compare-runs A=var/eval/<local run> B=var/eval/<course run>

Reads each run's results.jsonl and summary.json (written by `make eval`) and prints a Markdown
report: model and endpoint of each run, passes per category on the items both runs share, every item
that passed in one run and failed in the other, and latency and tokens. Only items present in both
runs are compared, so a partial run (`--only ...`) can be compared with a full one. Writes nothing
unless --out is given.
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def load(run: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rows = [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines() if line]
    meta = json.loads((run / "summary.json").read_text()).get("meta", {})
    return {r["id"]: r for r in rows}, meta


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, round(q * (len(s) - 1)))]


def report(a: Path, b: Path) -> tuple[str, int]:
    ra, ma = load(a)
    rb, mb = load(b)
    shared = sorted(set(ra) & set(rb))
    if not shared:
        raise SystemExit("the two runs share no items")
    cats: dict[str, list[str]] = defaultdict(list)
    for i in shared:
        cats[ra[i]["category"]].append(i)
    lines = [
        "# Run comparison",
        "",
        "| | A | B |",
        "|---|---|---|",
        f"| run | `{a.name}` | `{b.name}` |",
        f"| model | `{ma.get('model')}` | `{mb.get('model')}` |",
        f"| endpoint | `{ma.get('endpoint')}` | `{mb.get('endpoint')}` |",
        f"| response cache | {ma.get('llm_cache')} | {mb.get('llm_cache')} |",
        "",
        f"## Passes on the {len(shared)} items both runs have",
        "",
        "| Category | Items | A | B | Δ |",
        "|---|---|---|---|---|",
    ]
    total_a = total_b = 0
    for cat in sorted(cats):
        ids = cats[cat]
        pa = sum(ra[i]["passed"] for i in ids)
        pb = sum(rb[i]["passed"] for i in ids)
        total_a, total_b = total_a + pa, total_b + pb
        lines.append(f"| {cat} | {len(ids)} | {pa} | {pb} | {pb - pa:+d} |")
    delta = total_b - total_a
    lines.append(f"| **total** | {len(shared)} | **{total_a}** | **{total_b}** | **{delta:+d}** |")
    flips = [i for i in shared if ra[i]["passed"] != rb[i]["passed"]]
    lines += ["", f"## Items that changed ({len(flips)})", ""]
    if flips:
        lines += ["| Item | Category | A | B | B's failure / detail |", "|---|---|---|---|---|"]
        for i in flips:
            detail = (rb[i].get("failure_class") or "") + " " + (rb[i].get("detail") or "")
            detail = " ".join(detail.split())[:100].replace("|", "\\|")
            lines.append(
                f"| {i} | {ra[i]['category']} | {'PASS' if ra[i]['passed'] else 'FAIL'} | "
                f"{'PASS' if rb[i]['passed'] else 'FAIL'} | {detail or '—'} |"
            )
    else:
        lines.append("None: every shared item has the same verdict.")
    la = [ra[i]["latency_s"] for i in shared]
    lb = [rb[i]["latency_s"] for i in shared]
    ta = sum(ra[i].get("tokens", 0) for i in shared)
    tb = sum(rb[i].get("tokens", 0) for i in shared)
    lines += [
        "",
        "## Latency and tokens (shared items)",
        "",
        "| | A | B |",
        "|---|---|---|",
        f"| latency p50 (s) | {pct(la, 0.5):.1f} | {pct(lb, 0.5):.1f} |",
        f"| latency p95 (s) | {pct(la, 0.95):.1f} | {pct(lb, 0.95):.1f} |",
        f"| tokens | {ta:,} | {tb:,} |",
        "",
    ]
    return "\n".join(lines), len(flips)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("a", type=Path, help="run folder A (e.g. the local model)")
    ap.add_argument("b", type=Path, help="run folder B (e.g. the course endpoint)")
    ap.add_argument("--out", type=Path, help="also write the report to this file")
    args = ap.parse_args()
    text, _ = report(args.a, args.b)
    print(text)
    if args.out:
        args.out.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
