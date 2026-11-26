"""Phase 11 / P7 report (E13): full system vs the best baseline, ablations, failure taxonomy, cost.

    uv run python -m credassure.evaluation.eval_report --full var/eval/<run> \
        [--ablation var/eval/<run>-A1 ...] [--baseline evaluation/baseline/results] \
        [--calibration var/eval/<run>/j1-calibration.json] --out evaluation/reports/E13-<date>.md

Reads only harness and baseline result files. An ablation effect is *claimed* only when it lowers
more than one category, or the same drop shows on a rerun of that ablation (BRD §12): a single
category drop is reported as "not claimed".
"""

import argparse
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .scorers import BRD_CLASS

CATEGORIES = (
    "regulatory",
    "onboarding",
    "cashflow",
    "offers",
    "negotiation",
    "routing",
    "injection",
    "refusal",
    "isolation",
    "e2e",
)
CLASSES = ("search_miss", "reasoning_error", "tool_error", "hallucination")


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def by_category(rows: Iterable[Mapping[str, Any]]) -> dict[str, tuple[int, int]]:
    out: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        if r.get("passed") is None:  # infra errors are not scored
            continue
        out[str(r["category"])][0] += bool(r["passed"])
        out[str(r["category"])][1] += 1
    return {k: (v[0], v[1]) for k, v in out.items()}


def baseline_best(directory: Path | None) -> tuple[str, list[dict[str, Any]]] | None:
    """The best of S1-S3 by total passed (BRD §12)."""
    if directory is None or not directory.is_dir():
        return None
    runs = {p.stem: read_rows(p) for p in sorted(directory.glob("s[123]*.jsonl"))}
    if not runs:
        return None
    name = max(runs, key=lambda k: sum(bool(r.get("passed")) for r in runs[k]))
    return name, runs[name]


def taxonomy(rows: Iterable[Mapping[str, Any]]) -> Counter[str]:
    out: Counter[str] = Counter()
    for r in rows:
        if r.get("passed") is False:
            out[
                str(r.get("brd_class") or BRD_CLASS.get(str(r.get("failure_class")), "tool_error"))
            ] += 1
    return out


def ablation_effect(
    full: Mapping[str, tuple[int, int]], runs: Sequence[Mapping[str, tuple[int, int]]]
) -> tuple[list[str], str]:
    """Categories that dropped in every run of the ablation, and whether the effect is claimed."""
    dropped = [
        c
        for c in CATEGORIES
        if runs and all(c in r and c in full and r[c][0] < full[c][0] for r in runs)
    ]
    claimed = len(dropped) > 1 or (len(dropped) == 1 and len(runs) > 1)
    return dropped, "claimed" if claimed else (
        "not claimed (one category, one run)" if dropped else "no effect"
    )


def _cell(v: tuple[int, int] | None) -> str:
    return f"{v[0]}/{v[1]}" if v else "—"


def _human_score(calibration: Mapping[str, Any]) -> str:
    """D4: when people labelled every judged answer, their score is the one reported."""
    n, correct = calibration.get("n"), calibration.get("human_correct")
    if correct is None or not n:
        return ""
    scope = "every judged answer" if calibration.get("judged") == n else "a sample"
    return f" ({scope}): humans {correct}/{n} correct, J1 {calibration.get('j1_correct')}/{n}"


def render(
    full_dir: Path,
    ablation_dirs: Sequence[Path],
    baseline: tuple[str, list[dict[str, Any]]] | None,
    calibration: Mapping[str, Any] | None,
) -> str:
    rows = read_rows(full_dir / "results.jsonl")
    meta = json.loads((full_dir / "summary.json").read_text())["meta"]
    full = by_category(rows)
    total = sum(v[0] for v in full.values())
    base_total = sum(bool(r.get("passed")) for r in baseline[1]) if baseline else None
    base = by_category(baseline[1]) if baseline else {}

    groups: dict[str, list[dict[str, tuple[int, int]]]] = defaultdict(list)
    for d in ablation_dirs:
        m = json.loads((d / "summary.json").read_text())["meta"]
        groups[str(m["ablation"])].append(by_category(read_rows(d / "results.jsonl")))

    out = [
        f"# E13 — Phase 11 evaluation ({meta.get('started', '')})",
        "",
        f"Model `{meta.get('model')}` · endpoint `{meta.get('endpoint')}` · reranker "
        f"`{meta.get('reranker')}` · corpus lock `{meta.get('corpus_lock')}` · items {meta.get('items')}",
        "",
        "## Score",
        "",
        "| | Passed | Acceptance (ADR 0043) |",
        "|---|---|---|",
        f"| Full system | **{total}/{len(rows)}** | above the best baseline |",
        f"| Best baseline ({baseline[0] if baseline else 'not run here'}) | "
        f"{base_total if base_total is not None else '—'}/100 | — |",
        "",
        f"Verdict: **{'PASS' if base_total is None or total > base_total else 'FAIL'}**"
        + ("" if baseline else " (baseline results not found; comparison pending)"),
        "",
        "## Per category",
        "",
        "| Category | Baseline | Full |" + "".join(f" {a} |" for a in sorted(groups)),
        "|---|---|---|" + "---|" * len(groups),
    ]
    for c in CATEGORIES:
        abl = [_cell(groups[a][0].get(c)) if groups[a] else "—" for a in sorted(groups)]
        out.append(
            f"| {c} | {_cell(base.get(c))} | {_cell(full.get(c))} |"
            + "".join(f" {x} |" for x in abl)
        )

    if groups:
        out += [
            "",
            "## Ablation effects (BRD §12 claim rule)",
            "",
            "| Ablation | Dropped | Effect |",
            "|---|---|---|",
        ]
        for a in sorted(groups):
            dropped, verdict = ablation_effect(full, groups[a])
            out.append(f"| {a} | {', '.join(dropped) or '—'} | {verdict} |")

    tax, btax = taxonomy(rows), taxonomy(baseline[1]) if baseline else Counter()
    out += ["", "## Failure taxonomy (rule-based first guess; human confirm, scope #12)", ""]
    out += ["| Class | Baseline | Full |", "|---|---|---|"]
    out += [f"| {k} | {btax.get(k, 0) if baseline else '—'} | {tax.get(k, 0)} |" for k in CLASSES]
    failed = [r for r in rows if r.get("passed") is False]
    if failed:
        out += ["", "| Item | Category | Class | Detail |", "|---|---|---|---|"]
        out += [
            f"| {r['id']} | {r['category']} | {r.get('brd_class')} | {str(r.get('detail', ''))[:80]} |"
            for r in failed
        ]

    per: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        per[str(r["category"])].append(r)
    out += ["", "## Cost and latency (scope #5; tokens estimated as chars/4)", ""]
    out += ["| Category | Model calls | Tokens | Cost | Mean latency s |", "|---|---|---|---|---|"]
    for c in CATEGORIES:
        rs = per.get(c, [])
        if rs:
            out.append(
                f"| {c} | {sum(r.get('llm_calls', 0) for r in rs)} | {sum(r.get('tokens', 0) for r in rs)} | "
                f"{round(sum(r.get('cost', 0) for r in rs), 4)} | "
                f"{round(sum(r.get('latency_s', 0) for r in rs) / len(rs), 2)} |"
            )

    out += ["", "## Judge J1 calibration (ADR 0014)", ""]
    if calibration:
        k = calibration.get("kappa")
        out.append(
            f"Human sample {calibration.get('n')} items{_human_score(calibration)} · "
            f"agreement {calibration.get('agreement')} · "
            f"kappa {k} → {'J1 scores free text' if k is not None and k >= 0.7 else 'humans score free text (kappa < 0.7)'}"
        )
    else:
        out.append(
            "Not yet calibrated: run `make eval-judge`, label the sample, then `make eval-kappa`."
        )
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="credassure.evaluation.eval_report")
    ap.add_argument("--full", type=Path, required=True)
    ap.add_argument("--ablation", type=Path, nargs="*", default=[])
    ap.add_argument("--baseline", type=Path, default=Path("evaluation/baseline/results"))
    ap.add_argument("--calibration", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    cal = (
        json.loads(a.calibration.read_text()) if a.calibration and a.calibration.exists() else None
    )
    a.out.write_text(render(a.full, a.ablation, baseline_best(a.baseline), cal), encoding="utf-8")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
