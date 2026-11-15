"""Blind pooled judgement for the KR-05 retrieval labels (E8 M1).

`pool`: the union of every query's top 5 over all 18 configurations, deduplicated by (document, section)
and shuffled within each query. No configuration, rank or existing label is written anywhere, so
the judges cannot tell where a passage came from. Criteria and judges: evaluation/retrieval/v1/judging/criteria.md.

`make retrieval-pool` → evaluation/retrieval/v1/judging/{pool.jsonl,judging_sheet.csv}
`make retrieval-silver` → self-consistency gate, queries.v1.1-silver[-lenient].jsonl, diff, human_sample.json
`make judge JUDGE=<name>` → the human sample → judging/judgments_<name>.jsonl (SAMPLE= for the whole pool)
`make kappa JUDGE=<name>` → Cohen's kappa, silver vs that judge (method: judging/README.md)
"""

import argparse
import csv
import json
import os
import random
import re
import sys
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .gold.data import REPO
from .retrieval_eval import Hits, _ws, label_match, load_queries, open_searcher, run_searches

JUDGING = REPO / "evaluation" / "retrieval" / "v1" / "judging"
COLUMNS = [
    "item_id",
    "query_id",
    "query",
    "doc_id",
    "title",
    "section_path",
    "passage",
    "judge_A",
    "judge_A_note",
    "judge_B",
    "judge_B_note",
    "adjudicated",
    "adjudicator_note",
]
CELL_MAX = 32_000  # spreadsheet cell limit


def build_pool(
    hits: Hits, queries: list[dict[str, Any]], seed: str, depth: int = 5
) -> list[dict[str, str]]:
    """One row per distinct (query, document, section) in any top `depth`; the longest text is kept."""
    best: dict[tuple[str, str, str], Any] = {}
    for by_q in hits.values():
        for q in queries:
            for p in by_q[q["id"]][:depth]:
                key = (q["id"], p.doc_id, _ws(p.section_path or ""))
                if key not in best or len(p.text) > len(best[key].text):
                    best[key] = p
    text = {q["id"]: q["query"] for q in queries}
    rows: list[dict[str, str]] = []
    rng = random.Random(f"{seed}:judging")  # noqa: S311  # nosec B311 — order only
    for q in queries:
        group = [
            {
                "query_id": q["id"],
                "query": text[q["id"]],
                "doc_id": p.doc_id,
                "title": p.title,
                "section_path": p.section_path or "",
                "passage": p.text[:CELL_MAX],
            }
            for (qid, _, _), p in sorted(best.items(), key=lambda kv: kv[0])
            if qid == q["id"]
        ]
        rng.shuffle(group)
        rows += group
    return [{"item_id": f"J{i:04d}", **r} for i, r in enumerate(rows, 1)]


def write_pool(rows: list[dict[str, str]], out: Path = JUDGING) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "pool.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    with (out / "judging_sheet.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLUMNS, restval="")
        w.writeheader()
        w.writerows(rows)


LABELS = {"2": 2, "1": 1, "0": 0}  # relevant / partially relevant / not relevant
PASSAGE_SHOWN = 1_200
PROMPT = "[2] relevant  [1] partial  [0] not relevant  [s]kip  [b]ack  [c]riteria  [q]uit > "


def load_pool(path: Path = JUDGING / "pool.jsonl") -> list[dict[str, str]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


SILVER = JUDGING / "judgments_claude.jsonl"
SAMPLE = JUDGING / "human_sample.json"
LABELS_DIR = JUDGING.parent
SELF_CONSISTENCY_MIN = 0.85
KAPPA_MIN = 0.7


def load_silver(path: Path = SILVER) -> dict[str, int]:
    """Blind Claude grades (2/1/0), latest line per item wins."""
    out: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["item_id"]] = int(rec["judgment"])
    return out


def self_consistency(grades: Mapping[str, int], pairs: Mapping[str, str]) -> tuple[int, int, int]:
    """(binary agreements, exact-grade agreements, pairs) over copy → original duplicates; 2 = R."""
    binary = sum((grades[c] == 2) == (grades[o] == 2) for c, o in pairs.items())
    exact = sum(grades[c] == grades[o] for c, o in pairs.items())
    return binary, exact, len(pairs)


def covered(q: Mapping[str, Any], doc_id: str, section: str) -> bool:
    """The item already falls under one of the query's section labels (retrieval_eval semantics)."""
    return any(s["doc_id"] == doc_id and label_match(section, s) for s in q["relevant_sections"])


def widen(
    queries: list[dict[str, Any]],
    pool: list[dict[str, str]],
    grades: Mapping[str, int],
    min_grade: int,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, str]]]]:
    """v1.0 labels plus every pool item graded ≥ min_grade; never removes a label. Returns the new
    queries and the items added per query."""
    out = json.loads(json.dumps(queries))
    by_id = {q["id"]: q for q in out}
    added: dict[str, list[dict[str, str]]] = {q["id"]: [] for q in out}
    for r in pool:
        q = by_id[r["query_id"]]
        if grades[r["item_id"]] < min_grade or covered(q, r["doc_id"], r["section_path"]):
            continue
        label: dict[str, Any] = {"doc_id": r["doc_id"], "section_path": r["section_path"]}
        if not _ws(r["section_path"]):
            label["exact"] = True  # judged a preamble passage, not the whole document
        q["relevant_sections"].append(label)
        if r["doc_id"] not in q["relevant_doc_ids"]:
            q["relevant_doc_ids"].append(r["doc_id"])
        added[q["id"]].append(r)
    for q in out:
        q["labels"] = "v1.1-silver" if min_grade == 2 else "v1.1-silver-lenient"
    return out, added


def disputed(
    queries: list[dict[str, Any]], pool: list[dict[str, str]], grades: Mapping[str, int]
) -> list[dict[str, str]]:
    """Pool items a v1.0 label covers that the silver judge did not grade 2 (kept; for a human)."""
    by_id = {q["id"]: q for q in queries}
    return [
        r
        for r in pool
        if grades[r["item_id"]] < 2
        and covered(by_id[r["query_id"]], r["doc_id"], r["section_path"])
    ]


def stratified_sample(
    pool: list[dict[str, str]], grades: Mapping[str, int], seed: str, frac: float
) -> list[str]:
    """Seeded sample stratified by silver grade (largest remainder), pool order kept. The file holds
    ids only, so the human judge stays blind to the grades."""
    strata: dict[int, list[str]] = {}
    for r in pool:
        strata.setdefault(grades[r["item_id"]], []).append(r["item_id"])
    total = round(len(pool) * frac)
    quota = {g: len(ids) * frac for g, ids in strata.items()}
    take = {g: int(x) for g, x in quota.items()}
    for g in sorted(quota, key=lambda g: (take[g] - quota[g], g))[: total - sum(take.values())]:
        take[g] += 1
    rng = random.Random(f"{seed}:human-sample")  # noqa: S311  # nosec B311 — sampling only
    picked = {i for g in sorted(strata) for i in rng.sample(strata[g], take[g])}
    return [r["item_id"] for r in pool if r["item_id"] in picked]


def cohen_kappa(a: list[bool], b: list[bool], w: list[float] | None = None) -> float:
    """Cohen's kappa; with ``w``, every proportion is weighted (inverse sampling weights)."""
    w = w or [1.0] * len(a)
    n = sum(w)
    po = sum(wi for x, y, wi in zip(a, b, w, strict=True) if x == y) / n
    pa = sum(wi for x, wi in zip(a, w, strict=True) if x) / n
    pb = sum(wi for y, wi in zip(b, w, strict=True) if y) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def kappa_stats(
    ids: list[str], silver: Mapping[str, int], human: Mapping[str, int], pool: Mapping[str, int]
) -> tuple[float, float, float]:
    """(plain kappa, weighted agreement, weighted kappa) over judged sample ``ids``, binary 2 = R.
    Each item weighs N_g / n_g: its silver grade's pool count over that grade's judged count, so the
    sample is re-weighted to the full pool's grade mix even while it is incomplete."""
    judged = Counter(silver[i] for i in ids)
    total = Counter(pool.values())
    w = [total[silver[i]] / judged[silver[i]] for i in ids]
    a, h = [silver[i] == 2 for i in ids], [human[i] == 2 for i in ids]
    agreement = sum(wi for x, y, wi in zip(a, h, w, strict=True) if x == y) / sum(w)
    return cohen_kappa(a, h), agreement, cohen_kappa(a, h, w)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def diff_md(
    queries: list[dict[str, Any]],
    strict: Mapping[str, list[dict[str, str]]],
    lenient: Mapping[str, list[dict[str, str]]],
    dispute: list[dict[str, str]],
    consistency: tuple[int, int, int],
    grades: Mapping[str, int],
    low: int,
) -> str:
    def item(r: Mapping[str, str]) -> str:
        return f"{r['item_id']} `{r['doc_id']}` § {r['section_path'] or '(whole document)'}"

    b, e, n = consistency
    ns = sum(map(len, strict.values()))
    nl = sum(map(len, lenient.values()))
    counts = {g: sum(v == g for v in grades.values()) for g in (2, 1, 0)}
    lines = [
        "# Labels v1.1-silver — diff against v1.0 (KR-05)",
        "",
        "Generated by `make retrieval-silver` from `judgments_claude.jsonl` (blind Claude Code session,"
        " `judge: claude-code-blind`). Labels are **LLM-judged**; human agreement is pending (README.md).",
        "",
        f"- Pool: {len(grades)} originals (duplicates J0996+ excluded). Grades: 2 = {counts[2]},"
        f" 1 = {counts[1]}, 0 = {counts[0]}; low confidence {low}.",
        f"- Self-consistency on {n} duplicate pairs: binary {b}/{n}, exact grade {e}/{n}"
        f" (stop rule < {SELF_CONSISTENCY_MIN:.0%}).",
        f"- **Strict** (`queries.v1.1-silver.jsonl`) = v1.0 + grade 2: **+{ns}** section labels.",
        f"- **Lenient** (`queries.v1.1-silver-lenient.jsonl`) = v1.0 + grade ≥ 1: **+{nl}** section labels.",
        f"- v1.0 never shrinks. **{len(dispute)}** pool items under a v1.0 label were graded below 2:"
        " listed as disputed for a human decision, not removed.",
        "- v1.0 labels with an empty section cover the whole document, so off-topic sections of"
        " such a document can appear as disputed. A silver label on a passage before any heading is"
        " `exact`: it matches only unsectioned passages (for a document without headings, all of it).",
        "",
        "| Query | v1.0 sections | + strict | + lenient only | disputed |",
        "|---|---|---|---|---|",
    ]
    for q in queries:
        d = sum(r["query_id"] == q["id"] for r in dispute)
        lines.append(
            f"| {q['id']} | {len(q['relevant_sections'])} | {len(strict[q['id']])}"
            f" | {len(lenient[q['id']]) - len(strict[q['id']])} | {d} |"
        )
    lines += ["", "## Added (strict, grade 2)", ""]
    for q in queries:
        lines += [f"- **{q['id']}** {item(r)}" for r in strict[q["id"]]]
    lines += ["", "## Added in lenient only (grade 1)", ""]
    for q in queries:
        lenient_only = [r for r in lenient[q["id"]] if r not in strict[q["id"]]]
        lines += [f"- **{q['id']}** {item(r)}" for r in lenient_only]
    lines += ["", "## Disputed v1.0 labels (silver grade < 2; kept)", ""]
    lines += [f"- **{r['query_id']}** {item(r)} — grade {grades[r['item_id']]}" for r in dispute]
    lines += [*([] if dispute else ["None."]), ""]
    return "\n".join(lines)


def silver_main(env: Mapping[str, str]) -> int:
    """Steps 1, 2 and the human sample: self-consistency gate, v1.1-silver labels + diff."""
    raw = [json.loads(x) for x in SILVER.read_text(encoding="utf-8").splitlines() if x.strip()]
    grades = load_silver()
    pairs = json.loads((JUDGING / "duplicates_map.json").read_text(encoding="utf-8"))["pairs"]
    pool = load_pool()
    missing = ({r["item_id"] for r in pool} | set(pairs)) - grades.keys()
    if missing or any(g not in (0, 1, 2) for g in grades.values()):
        print(f"retrieval-silver: {len(missing)} items unjudged or bad grades", file=sys.stderr)
        return 1
    consistency = self_consistency(grades, pairs)
    b, e, n = consistency
    print(f"self-consistency: binary {b}/{n}, exact {e}/{n}")
    if b / n < SELF_CONSISTENCY_MIN:
        print(f"retrieval-silver: below {SELF_CONSISTENCY_MIN:.0%}, stopping", file=sys.stderr)
        return 1
    originals = {r["item_id"]: grades[r["item_id"]] for r in pool}
    queries = load_queries()
    strict, s_added = widen(queries, pool, originals, 2)
    lenient, l_added = widen(queries, pool, originals, 1)
    write_jsonl(LABELS_DIR / "queries.v1.1-silver.jsonl", strict)
    write_jsonl(LABELS_DIR / "queries.v1.1-silver-lenient.jsonl", lenient)
    low = sum(r["confidence"] == "low" for r in raw if r["item_id"] in originals)
    dispute = disputed(queries, pool, originals)
    (JUDGING / "labels_v1.1-silver_diff.md").write_text(
        diff_md(queries, s_added, l_added, dispute, consistency, originals, low), encoding="utf-8"
    )
    seed = env.get("CREDASSURE_SEED", "20261026")
    ids = stratified_sample(pool, originals, seed, 0.25)
    SAMPLE.write_text(
        json.dumps(
            {
                "seed": f"{seed}:human-sample",
                "fraction": 0.25,
                "stratified_by": "silver grade",
                "n": len(ids),
                "item_ids": ids,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        f"retrieval-silver: strict +{sum(map(len, s_added.values()))}, lenient"
        f" +{sum(map(len, l_added.values()))}, disputed {len(dispute)}, human sample {len(ids)}"
    )
    return 0


def kappa_main(argv: list[str]) -> int:
    """Silver vs one human over the human sample, binary (2 = R). Run only after `make judge`."""
    ap = argparse.ArgumentParser(prog="make kappa")
    ap.add_argument("--judge", required=True)
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[a-z]+", args.judge):
        print("judge name: lowercase letters only", file=sys.stderr)
        return 2
    ids = json.loads(SAMPLE.read_text(encoding="utf-8"))["item_ids"]
    silver = load_silver(SILVER)
    human = load_judgments(JUDGING / f"judgments_{args.judge}.jsonl")
    both = [i for i in ids if i in human]
    if not both:
        print(f"kappa: no {args.judge} judgments on the sample yet", file=sys.stderr)
        return 1
    pool = {r["item_id"]: silver[r["item_id"]] for r in load_pool(JUDGING / "pool.jsonl")}
    plain, w_agree, w_k = kappa_stats(both, silver, human, pool)
    agree = sum((silver[i] == 2) == (human[i] == 2) for i in both)
    print(
        f"kappa silver vs {args.judge}: n {len(both)}/{len(ids)}\n"
        f"  sample: agreement {agree}/{len(both)}, plain κ = {plain:.3f}\n"
        f"  weighted to the pool's silver-grade mix: agreement {w_agree:.1%},"
        f" weighted κ = {w_k:.3f}\n"
        f"  verdict (weighted κ): "
        f"{'confirmed (≥ 0.7)' if w_k >= KAPPA_MIN else 'full human judging (< 0.7)'}"
        + ("" if len(both) == len(ids) else " — sample incomplete, provisional")
    )
    return 0


def load_judgments(path: Path) -> dict[str, int]:
    """Latest answer per item wins, so going back and re-answering only appends."""
    latest: dict[str, int] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                latest[rec["item_id"]] = rec["label"]
    return latest


def screen(r: Mapping[str, str], i: int, n: int, judged: int, previous: int | None) -> str:
    """Query, title, section and passage only: no configuration, rank or existing label."""
    earlier = f"(your earlier answer: {previous})\n" if previous is not None else ""
    return (
        f"\n{'─' * 72}\nitem {i + 1} of {n} · judged {judged}\n\n"
        f"QUERY:   {r['query']}\nDOC:     {r['title']}\nSECTION: {r['section_path'] or '—'}\n\n"
        f"{r['passage'][:PASSAGE_SHOWN]}\n\n{earlier}{PROMPT}"
    )


def judge(
    items: list[dict[str, str]],
    out: Path,
    judge_name: str,
    read_key: Callable[[], str],
    write: Callable[[str], object],
    criteria: str = "",
) -> int:
    """Resumable single-judge loop; every answer is appended and flushed before the next item."""
    done = load_judgments(out)
    i = next((n for n, r in enumerate(items) if r["item_id"] not in done), len(items))
    with out.open("a", encoding="utf-8") as f:
        while i < len(items):
            r = items[i]
            judged = sum(x["item_id"] in done for x in items)
            write(screen(r, i, len(items), judged, done.get(r["item_id"])))
            key = read_key()
            if key in LABELS:
                rec = {
                    "item_id": r["item_id"],
                    "judge": judge_name,
                    "label": LABELS[key],
                    "ts": datetime.now(UTC).isoformat(timespec="seconds"),
                }
                f.write(json.dumps(rec) + "\n")
                f.flush()
                done[r["item_id"]] = LABELS[key]
                i += 1
            elif key == "s":
                i += 1
            elif key == "b":
                i = max(0, i - 1)
            elif key == "c":
                write("\n" + criteria)
            elif key == "q":
                break
    judged = sum(x["item_id"] in done for x in items)
    write(f"\nsaved: {judged} of {len(items)} judged → {out}\n")
    return judged


def read_key() -> str:
    """One keypress on a terminal; a line when piped (EOF → quit)."""
    if not sys.stdin.isatty():
        return sys.stdin.readline().strip()[:1] or "q"
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def judge_main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="make judge")
    ap.add_argument("--judge", required=True)
    ap.add_argument("--sample", action="store_true", help="only the stratified human sample")
    args = ap.parse_args(argv)
    if not re.fullmatch(r"[a-z]+", args.judge):  # used in a file name
        print("judge name: lowercase letters only", file=sys.stderr)
        return 2
    items = load_pool()
    if args.sample:
        ids = set(json.loads(SAMPLE.read_text(encoding="utf-8"))["item_ids"])
        items = [r for r in items if r["item_id"] in ids]
    criteria = (JUDGING / "criteria.md").read_text(encoding="utf-8")
    judge(
        items,
        JUDGING / f"judgments_{args.judge}.jsonl",
        args.judge,
        read_key,
        lambda s: print(s, end="", flush=True),
        criteria,
    )
    return 0


def main(argv: list[str], env: Mapping[str, str] = os.environ) -> int:
    if argv[:1] == ["judge"]:
        return judge_main(argv[1:])
    if argv[:1] == ["silver"]:
        return silver_main(env)
    if argv[:1] == ["kappa"]:
        return kappa_main(argv[1:])
    if argv[:1] != ["pool"]:
        print(
            "usage: python -m credassure.evaluation.retrieval_judging"
            " pool | silver | judge --judge NAME [--sample] | kappa --judge NAME",
            file=sys.stderr,
        )
        return 2
    searcher, _, reranker, _ = open_searcher(env)
    queries = load_queries()
    hits = run_searches(
        searcher,
        queries,
        rerank_options=(False, True) if reranker else (False,),
        progress=lambda line: print(line, file=sys.stderr, flush=True),
    )
    if len(hits) != 18:
        print(
            f"retrieval-pool: {len(hits)} configurations, need 18 (rerank extra?)", file=sys.stderr
        )
        return 1
    rows = build_pool(hits, queries, env.get("CREDASSURE_SEED", "20261026"))
    write_pool(rows)
    per_q = [sum(r["query_id"] == q["id"] for r in rows) for q in queries]
    print(f"retrieval-pool: {len(rows)} items, {min(per_q)}-{max(per_q)} per query → {JUDGING}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
