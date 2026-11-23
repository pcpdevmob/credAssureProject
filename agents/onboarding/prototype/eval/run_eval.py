"""Score the Employee Onboarding Agent against its eval items.

    python -m eval.run_eval                                  # in-process, all three files
    python -m eval.run_eval --api http://127.0.0.1:8000      # through the running API, as the team harness does

Files:
  onboarding_eval.jsonl   the 10 onboarding items for the team's 100-item test set (BRD OBJ-01: 10/10)
  regression_eval.jsonl   extra edge cases (not part of the 100; run them before every merge)
  pii_eval.jsonl          ONB-06 redaction checks
A readiness item passes only if the decision AND the exact set of failed rules match gold.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
DECISION = {"GO": "GO", "NO_GO": "NO-GO", "NEEDS_INPUT": "NEEDS_INPUT", "ERROR": "ERROR"}


def load(name: str) -> list[dict]:
    return [json.loads(l) for l in (HERE / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def _post(api: str, path: str, body: dict) -> dict:
    req = urllib.request.Request(api.rstrip("/") + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=120) as resp:
        return json.loads(resp.read())


def run_item(inp: dict, api: str | None) -> tuple[str, list[str], str]:
    if api:
        body = {"case_id": inp["case_id"], "preparer_id": inp["employee_id"], "as_of": inp["as_of"]}
        if inp.get("checklist"):
            body["checklist"] = inp["checklist"]
        out = _post(api, "/api/agents/onboarding/readiness", body)
        return out["decision"], [b["rule_id"] for b in out["blockers"]], out["explanation_source"]
    from readiness.gate import run_readiness_gate
    res = run_readiness_gate(inp["case_id"], inp["employee_id"], as_of=date.fromisoformat(inp["as_of"]),
                             case_checklist=inp.get("checklist"))
    return DECISION[res.decision.value], res.blockers, res.explanation_source


def score_readiness(name: str, api: str | None) -> tuple[int, int]:
    items, passed = load(name), 0
    print(f"\n== {name} ==")
    for it in items:
        dec, blockers, src = run_item(it["input"], api)
        ok = dec == it["gold"]["decision"] and set(blockers) == set(it["gold"]["blockers"])
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {it['id']}  {it['input']['employee_id']}  got={dec} {sorted(blockers)}"
              f"  gold={it['gold']['decision']} {sorted(it['gold']['blockers'])}  [{src}]")
    return passed, len(items)


def score_pii(api: str | None) -> tuple[int, int]:
    items, passed = load("pii_eval.jsonl"), 0
    print("\n== pii_eval.jsonl ==")
    for it in items:
        msg = it["input"]["message"]
        if api:
            out = _post(api, "/api/agents/onboarding/message",
                        {"case_id": "CASE-001", "preparer_id": "EMP-001", "message": msg, "as_of": "2026-11-02"})
            kinds, text = out["pii_redacted"], json.dumps(out)
        else:
            from readiness.pii import redact
            text, kinds = redact(msg)
        ok = sorted(kinds) == sorted(it["gold"]["pii"]) and not any(s in text for s in it["gold"]["must_not_contain"])
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {it['id']}  found={kinds}  gold={it['gold']['pii']}")
    return passed, len(items)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", help="base URL of a running backend, e.g. http://127.0.0.1:8000")
    args = ap.parse_args(argv)
    results = {"onboarding (BRD test set)": score_readiness("onboarding_eval.jsonl", args.api),
               "regression": score_readiness("regression_eval.jsonl", args.api),
               "PII redaction": score_pii(args.api)}
    print()
    for name, (p, n) in results.items():
        print(f"{name:28s} {p}/{n}")
    return 0 if all(p == n for p, n in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
