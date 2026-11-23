"""LangGraph integration.

`readiness_node` is what the Supervisor adds to its LangGraph graph (BRD SUP-03, SUP-04):
    builder.add_node("readiness", readiness_node)
    builder.add_conditional_edges("readiness", route_after_readiness,
                                  {"go": "working_capital", "pause": "pause"})

The state keys used here are a DRAFT; align them with the Supervisor's state.
Run `python -m readiness.graph` for a demo with a stub Working Capital stage.
"""
from __future__ import annotations

import operator
from datetime import date
from typing import Annotated, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from .gate import run_readiness_gate


def _merge(a: dict, b: dict) -> dict:
    return {**(a or {}), **(b or {})}


class CaseState(TypedDict, total=False):
    case_id: str
    preparer_id: str
    as_of: Optional[str]                              # ISO date; None = today
    case_checklist: Optional[dict]                    # case-intake answers; None = preparer only
    stage_results: Annotated[dict, _merge]            # stage name -> StageResult as JSON
    current_stage: str
    paused_reason: Optional[str]
    log: Annotated[list, operator.add]


def readiness_node(state: CaseState) -> dict:
    as_of = date.fromisoformat(state["as_of"]) if state.get("as_of") else None
    res = run_readiness_gate(state["case_id"], state["preparer_id"], as_of=as_of,
                             case_checklist=state.get("case_checklist"))
    go = res.decision.value == "GO"
    return {"stage_results": {"readiness": res.model_dump(mode="json")},
            "current_stage": "working_capital" if go else "readiness",
            "paused_reason": None if go else f"readiness:{res.decision.value}",
            "log": [f"readiness -> {res.decision.value}"]}


def route_after_readiness(state: CaseState) -> str:
    """Code gate: only an explicit GO moves on. Anything else pauses at this stage."""
    res = state.get("stage_results", {}).get("readiness") or {}
    return "go" if res.get("decision") == "GO" else "pause"


# ---------- demo only: stubs standing in for the rest of the Supervisor ----------
def _working_capital_stub(state: CaseState) -> dict:
    return {"log": ["working_capital (stub) reached"]}


def _pause(state: CaseState) -> dict:
    return {"log": [f"paused at readiness: {state.get('paused_reason')}"]}


def build_demo_graph():
    g = StateGraph(CaseState)
    g.add_node("readiness", readiness_node)
    g.add_node("working_capital", _working_capital_stub)
    g.add_node("pause", _pause)
    g.add_edge(START, "readiness")
    g.add_conditional_edges("readiness", route_after_readiness,
                            {"go": "working_capital", "pause": "pause"})
    g.add_edge("working_capital", END)
    g.add_edge("pause", END)
    return g.compile()


if __name__ == "__main__":
    graph = build_demo_graph()
    for emp in ("EMP-001", "EMP-014", "EMP-015", "EMP-999"):
        out = graph.invoke({"case_id": "CASE-DEMO-1", "preparer_id": emp, "as_of": "2026-11-02"},
                           config={"recursion_limit": 10})
        r = out["stage_results"]["readiness"]
        print(f"\n=== {emp}: {r['decision']}  blockers={r['blockers']}")
        print("   ", r["explanation"])
        print("    path:", " | ".join(out["log"]))
