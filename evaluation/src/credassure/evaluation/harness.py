"""Phase 11 / plan v3.4 P7 harness: the 100 frozen items through the gateway API (BRD §13, API-01).

Drives any httpx-compatible client (FastAPI's TestClient in process, or httpx.Client against a
running gateway) and never imports the gateway, an agent or the engines (ADR 0005; independent gold).
Routing items that give only an amount have no API path (no case carries an arbitrary amount), so
the caller passes ``route_fn``: the same routing function the Supervisor calls. Every other item
goes through the API exactly as the web app would.

Per item: the scorer's verdict, the BRD failure class (scope #12, rule-based first guess for human
confirmation), latency, model calls and tokens (from the caller's ``meter``) and notional cost
(scope #5, tokens x EVAL_PRICE_PER_1K).
"""

import json
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from .check_corpus_refs import known_doc_ids
from .gold.data import DATA, REPO
from .scorers import ABSTAIN, BRD_CLASS, score

ITEMS = REPO / "evaluation" / "testset" / "v1" / "items.jsonl"
KINDS = ("order", "opening_position", "costs", "receipts", "receivables", "payables", "inventory")
NEW_CASE = {
    "msme_name": "Eval Electronics Pvt Ltd",
    "order_ref": "PO-EVAL",
    "order_value_paise": 3_20_00_000_00,
    "indicative_amount_paise": 2_00_00_000_00,
    "due_date": "2027-05-15",
}
STAGE_KEYS = {"onboarding": "onboarding_gate", "working_capital": "funding_gate"}
TOKEN_REUSE_S = 20 * 60  # under the 30-minute access-token lifetime (JWT_EXPIRY_MINUTES max 30)
STAGE_KEYS |= {"lendwise": "lendwise_gate"}
Client = Any  # httpx.Client or TestClient (see safety_v2: httpx spells every keyword out)
Meter = Callable[[], tuple[int, int]]  # cumulative (model calls, tokens)
RouteFn = Callable[[Decimal, str], str]


@dataclass
class Row:
    id: str
    category: str
    subtype: str | None
    passed: bool
    failure_class: str | None  # scorer class
    brd_class: str | None  # retrieval_miss | reasoning_error | tool_error | hallucination
    detail: str
    latency_s: float
    llm_calls: int
    tokens: int
    cost: float
    answer: dict[str, Any] = field(default_factory=dict)


def load(path: Path = ITEMS) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x]


def brd_class(
    item: Mapping[str, Any], result: Mapping[str, Any], answer: Mapping[str, Any]
) -> str | None:
    """Scope #12 first guess. A citation item that abstained or cited only real but wrong documents
    is a search miss, not a hallucination; a cited document that does not exist is a hallucination."""
    if result.get("passed"):
        return None
    cls = str(result.get("failure_class") or "schema_failure")
    if item.get("scorer") == "citation" and cls == "invented_citation":
        cited = set(answer.get("citations") or [])
        if not cited or ABSTAIN in str(answer.get("answer", "")):
            return "search_miss"
        if cited <= known_doc_ids():
            return "search_miss"
    return BRD_CLASS.get(cls, "tool_error")


class Harness:
    def __init__(
        self,
        client: Client,
        password: str,
        *,
        route_fn: RouteFn,
        meter: Meter = lambda: (0, 0),
        price_per_1k: float = 0.0,
    ) -> None:
        self.c, self.password, self.route_fn = client, password, route_fn
        self.meter, self.price = meter, price_per_1k
        self._tokens: dict[str, dict[str, str]] = {}
        self._issued: dict[str, float] = {}
        self._base: str | None = None
        self.known = known_doc_ids()

    # ---- plumbing
    def h(self, user: str) -> dict[str, str]:
        """A bearer header for ``user``. Access tokens last at most 30 minutes and a live run takes
        hours, so a token is reused for TOKEN_REUSE_S only, then the user signs in again (a cached
        token made the last e2e items of the 2026-11-18 live run fail with 401)."""
        now = time.monotonic()
        if user not in self._tokens or now - self._issued.get(user, 0.0) > TOKEN_REUSE_S:
            r = self.c.post("/v1/auth/token", json={"username": user, "password": self.password})
            r.raise_for_status()
            self._tokens[user] = {"Authorization": f"Bearer {r.json()['access_token']}"}
            self._issued[user] = now
        return self._tokens[user]

    def _post(self, cid: str, kind: str, path: Path, h: dict[str, str]) -> list[str]:
        mime = {".json": "application/json", ".csv": "text/csv", ".md": "text/markdown"}[
            path.suffix
        ]
        r = self.c.post(
            f"/v1/cases/{cid}/files",
            params={"kind": kind},
            files={"file": (path.name, path.read_bytes(), mime)},
            headers=h,
        )
        r.raise_for_status()
        return list(r.json().get("injection_flags") or [])

    def case(
        self, frozen: str, actor: str = "demo.preparer", *, offers: bool = True
    ) -> tuple[str, list[str]]:
        h = self.h(actor)
        r = self.c.post("/v1/cases", json=NEW_CASE, headers=h)
        r.raise_for_status()
        cid = str(r.json()["case_id"])
        flags: list[str] = []
        for kind in KINDS:
            ext = "json" if kind in ("order", "opening_position") else "csv"
            flags += self._post(cid, kind, DATA / "cases" / frozen / f"{kind}.{ext}", h)
        if offers:
            for offer in sorted((DATA / "offers" / frozen).glob("*.v1.json")):
                doc = json.loads(offer.read_text())["kfs_doc_id"]
                flags += self._post(cid, "offer", offer, h)
                for p in (DATA / "kfs" / f"{doc}.md", DATA / "kfs" / f"{doc}-SCH.md"):
                    flags += self._post(cid, "kfs", p, h)
        return cid, flags

    def stage(self, cid: str, agent: str, h: dict[str, str]) -> dict[str, Any]:
        self.c.post(f"/v1/agents/{agent}/cases/{cid}/run", headers=h)
        r = self.c.get(f"/v1/agents/{agent}/cases/{cid}/result", headers=h)
        return dict(r.json()) if r.status_code == 200 else {}

    def run_case(self, cid: str, h: dict[str, str]) -> dict[str, Any]:
        r = self.c.post(f"/v1/cases/{cid}/run", headers=h)
        if r.status_code == 202:
            self.c.get(r.json()["status_url"], headers=h)
        return dict(self.c.get(f"/v1/cases/{cid}", headers=h).json())

    def base(self) -> str:
        if self._base is None:
            self._base, _ = self.case("CA-2026-0001")
        return self._base

    def chat(self, cid: str, actor: str, question: str) -> dict[str, Any]:
        r = self.c.post(f"/v1/cases/{cid}/chat", json={"message": question}, headers=self.h(actor))
        if r.status_code == 404:  # another case: refused by scoping (SUP-08)
            return {"refused": True, "answer": str(r.json().get("detail", "")), "citations": []}
        return dict(r.json())

    # ---- answers per category (the shapes in each item's answer_schema)
    def answer(self, item: Mapping[str, Any]) -> dict[str, Any]:
        cat, inp = item["category"], item["input"]
        actor = inp.get("actor", "demo.preparer")
        if cat == "routing":
            if "amount" in inp:
                return {"route": self.route_fn(Decimal(inp["amount"]), inp["boundary_rule"])}
            cid, _ = self.case(inp["case_id"])
            return {"route": self._route(self.run_case(cid, self.h(actor)))}
        if cat == "onboarding":
            h = self.h(actor)
            r = self.c.post("/v1/cases", json=NEW_CASE, headers=h)
            r.raise_for_status()
            res = self.stage(str(r.json()["case_id"]), "onboarding", h)
            return {
                "gate": res.get("decision"),
                "failed_rules": sorted(b["field"] for b in res.get("blockers") or []),
            }
        if cat == "cashflow":
            cid, _ = self.case(inp["case_id"], actor, offers=False)
            h = self.h(actor)
            self.stage(cid, "onboarding", h)
            res = self.stage(cid, "working-capital", h)
            out: dict[str, Any] = {"gate": res.get("decision")}
            f = self.c.get(f"/v1/cases/{cid}/funding", headers=h)
            facts = (
                {x["key"]: x["value"] for x in f.json().get("facts", [])}
                if f.status_code == 200
                else {}
            )
            if res.get("decision") == "GO":
                out |= {
                    "recommended_amount": _num(facts.get("wc.recommended_amount")),
                    "peak_shortfall": _num(facts.get("wc.peak_shortfall")),
                    "peak_week": _num(facts.get("wc.peak_week")),
                    "bridge": [
                        {"line": k.removeprefix("wc.bridge."), "amount": _num(v)}
                        for k, v in facts.items()
                        if k.startswith("wc.bridge.")
                    ],
                }
            else:
                out["missing_or_conflicting"] = [
                    {"code": b.get("code"), "field": b.get("field")}
                    for b in res.get("blockers") or []
                ]
                out["blockers"] = out["missing_or_conflicting"]
            return out
        if cat in ("offers", "negotiation"):
            cid, _ = self.case(inp["case_id"], actor)
            h = self.h(actor)
            for agent in ("onboarding", "working-capital", "lendwise"):
                self.stage(cid, agent, h)
            if cat == "negotiation":
                r = self.c.post(f"/v1/agents/lendwise/cases/{cid}/negotiate", headers=h)
                return dict(r.json()) if r.status_code == 200 else {"error": r.status_code}
            view = self.c.get(f"/v1/cases/{cid}/offers", headers=h).json()
            return {
                "gate": view.get("gate"),
                "ranking": view.get("ranking"),
                "offers": {
                    o["offer_id"]: {"apr_pct": o.get("apr_pct"), "flags": o.get("flags")}
                    for o in view.get("offers") or []
                },
            }
        if cat == "injection" and not inp.get("question"):
            cid, flags = self.case(inp["case_id"], actor)
            h = self.h(actor)
            for agent in ("onboarding", "working-capital", "lendwise"):
                self.stage(cid, agent, h)
            if inp.get("stage") == "negotiation_reply":
                reply = self.c.post(f"/v1/agents/lendwise/cases/{cid}/negotiate", headers=h).json()
                view = self.c.get(f"/v1/cases/{cid}/offers", headers=h).json()
                lender = reply.get("reply") or (view.get("negotiation") or {}).get("reply") or {}
                return {
                    "ranking": view.get("ranking"),
                    "injection_flagged": bool(lender.get("injection_flags")),
                    "answer": str(reply.get("message", "")),
                }
            res = self.c.get(f"/v1/agents/lendwise/cases/{cid}/result", headers=h).json()
            view = self.c.get(f"/v1/cases/{cid}/offers", headers=h).json()
            return {
                "ranking": view.get("ranking"),
                "injection_flagged": bool(flags),
                "answer": str(res.get("narrative") or ""),
            }
        if cat == "e2e":
            cid, _ = self.case(inp["case_id"], actor)
            h = self.h(actor)
            case = self.run_case(cid, h)
            gates = {s.get("stage"): s.get("decision") for s in case.get("stages") or []}
            f = self.c.get(f"/v1/cases/{cid}/funding", headers=h)
            o = self.c.get(f"/v1/cases/{cid}/offers", headers=h)
            amount = (
                (f.json().get("recommended_amount") or {}).get("paise")
                if f.status_code == 200
                else None
            )
            ranking = (o.json().get("ranking") or []) if o.status_code == 200 else []
            lw = gates.get("lendwise")
            return {
                "onboarding_gate": gates.get("onboarding"),
                "funding_gate": gates.get("working_capital"),
                "recommended_amount": amount // 100
                if amount is not None and gates.get("working_capital") == "GO"
                else None,
                "lendwise_gate": lw,
                "top_offer": ranking[0] if ranking and lw == "GO" else None,
                "route": self._route(case),
            }
        # regulatory, refusal, isolation and chat injection: the copilot through /chat
        cid = self.base()
        if cat == "injection":
            cid, _ = self.case(inp["case_id"], actor)
            h = self.h(actor)
            for agent in ("onboarding", "working-capital", "lendwise"):
                self.stage(cid, agent, h)
        ans = self.chat(cid, actor, inp["question"])
        ans["citations"] = sorted({c["doc_id"] for c in ans.get("citations") or []})
        if cat == "injection":
            ans["ranking"] = ans.get("ranking") or []
        return ans

    @staticmethod
    def _route(case: Mapping[str, Any]) -> str | None:
        if case.get("status") == "HELD":
            return "HELD"
        route = case.get("route")
        return str(route) if route else None

    def run_item(self, item: Mapping[str, Any]) -> Row:
        calls0, tok0 = self.meter()
        t0 = time.monotonic()
        try:
            answer = self.answer(item)
        except Exception as exc:  # an item that cannot run is a tool error, never skipped
            answer = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        latency = round(time.monotonic() - t0, 2)
        result = (
            score(dict(item), answer, self.known)
            if "error" not in answer
            else {
                "passed": False,
                "failure_class": "schema_failure",
                "detail": answer["error"],
            }
        )
        calls, tokens = (a - b for a, b in zip(self.meter(), (calls0, tok0), strict=True))
        return Row(
            id=str(item["id"]),
            category=str(item["category"]),
            subtype=item.get("subtype"),
            passed=bool(result["passed"]),
            failure_class=result.get("failure_class"),
            brd_class=brd_class(item, result, answer),
            detail=str(result.get("detail") or ""),
            latency_s=latency,
            llm_calls=calls,
            tokens=tokens,
            cost=round(tokens / 1000 * self.price, 4),
            answer={
                k: v
                for k, v in answer.items()
                if k in ("answer", "citations", "ranking", "route", "gate", "error", "refused")
            },
        )

    def run(
        self, items: Iterable[Mapping[str, Any]], *, on_row: Callable[[Row], None] | None = None
    ) -> list[Row]:
        rows = []
        for item in items:
            row = self.run_item(item)
            rows.append(row)
            if on_row:
                on_row(row)
        return rows


def _num(value: Any) -> Any:
    if value is None:
        return None
    try:
        d = Decimal(str(value))
    except ArithmeticError:
        return value
    return int(d) if d == d.to_integral_value() else float(d)


def summary(rows: list[Row]) -> dict[str, Any]:
    by_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        by_cat[r.category][0] += r.passed
        by_cat[r.category][1] += 1
    lat = sorted(r.latency_s for r in rows)
    return {
        "passed": sum(r.passed for r in rows),
        "total": len(rows),
        "by_category": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_cat.items())},
        "taxonomy": dict(Counter(r.brd_class for r in rows if not r.passed)),
        "tokens": sum(r.tokens for r in rows),
        "llm_calls": sum(r.llm_calls for r in rows),
        "cost": round(sum(r.cost for r in rows), 4),
        "latency_p50_s": lat[len(lat) // 2] if lat else 0,
        "latency_p95_s": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else 0,
    }


def write(rows: list[Row], out_dir: Path, meta: Mapping[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.jsonl").write_text(
        "".join(json.dumps(asdict(r), ensure_ascii=False, default=str) + "\n" for r in rows),
        encoding="utf-8",
    )
    s = summary(rows) | {"meta": dict(meta)}
    (out_dir / "summary.json").write_text(
        json.dumps(s, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return s
