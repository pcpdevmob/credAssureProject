"""Ask CredAssure (CP-01..03, CP-07, CP-10, scope #2, #20, design-detail §2.4.6, ADR 0035).
On demand, never a stage; with or without an open case.

    refusal policy (code) → injection check on the message (code) → intent routing (code, CP-07):
    a case question without a case gets a fixed "open a case" reply; case status and blockers are
    answered from code-rendered text (no model, so they work with the model off) → model off?
    abstain → if code did not route it, the model picks one of the fixed tools (code validates;
    invalid → search_regulations; no case tool without a case) →
    ≤5 passages, injection-scanned, split into numbered sentence spans [n.m] and spotlighted →
    the model answers citing a span after every sentence and writing case figures only as
    {fact.key} slots → code cuts every sentence without a valid span id (P5, scope #64), maps
    span ids to [chunk_id] and renders the slots → the Critic (verify_claims) → the answer, or
    exactly ABSTAIN when nothing is left.

case_id comes from the gateway, never from the model (SUP-08); None means no case is open, and then
no case tool runs at all. The model never sees a figure it
could copy into an answer: case figures exist only as slot names, filled in by code.
"""

import re
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict

from credassure.agents.copilot import intent as it
from credassure.agents.copilot import policy, spans
from credassure.agents.copilot.policy import ABSTAIN
from credassure.core import slots as slot_fmt
from credassure.core.errors import LLMError
from credassure.core.ports import LLMPort, ToolPort
from credassure.core.prompts import registry
from credassure.core.structured import complete_model
from credassure.security.injection import scan
from credassure.security.spotlight import spotlight

from . import __version__

TOOLS = (
    "search_regulations",
    "search_policies",
    "search_help",
    "get_case_facts",
    "get_case_status",
    "explain_blocker",
)
CASE_TOOLS = frozenset({"get_case_facts", "get_case_status", "explain_blocker"})
SEARCH_TOOLS = frozenset({"search_regulations", "search_policies", "search_help"})
DEFAULT_TOOL = "search_regulations"
MAX_PASSAGES = 5
INJECTION_REPLY = (
    "That message tries to change how the copilot works, so it was not followed. The offer "
    "ranking is set by code from the verified APR and cash-flow fit: {ranking}."
)
NO_RANKING = "no ranking has been calculated for this case yet"
NO_BLOCKER = "Nothing is blocked on this case right now."
INJECTION_REPLY_NO_CASE = (
    "That message tries to change how the copilot works, so it was not followed. Ask a question "
    "about CredAssure, a rule or a policy."
)
OPEN_CASE = (
    "Open the case from **Cases** first: questions about a case's status, blockers or figures are "
    "answered only inside that case, so one case's data never appears in another conversation."
)
# SUP-02: chat never changes data or decides a case; these fixed replies say where that happens.
FORM_NAME = {  # the form names on the Case data tab (apps/web lib/plain.ts FILE_LABEL)
    "order": "Customer order",
    "opening_position": "Opening cash and credit lines",
    "costs": "Weekly costs",
    "receipts": "Expected receipts",
    "receivables": "Customer invoices due",
    "payables": "Supplier bills",
    "inventory": "Stock movement",
    "offer": "Lender offer",
}
CORRECTION_REPLY = (
    "I can't change case data from chat: every figure comes from the saved case data and is "
    "recalculated by code. To correct it, the preparer opens the **Case data** tab, corrects "
    "“{form}” and saves, then runs the case again from the **Workflow** tab. The {step} step and "
    "the steps after it run again; earlier steps are kept."
)
CORRECTION_CLARIFY = (
    "Which data do you want to correct? Name it, for example “Opening cash and credit lines”, "
    "“Expected receipts”, “Supplier bills” or a lender offer, and I will point you to its form. "
    "I can't change case data from chat."
)
APPROVAL_REPLY = (
    "I can't approve, reject or return a proposal from chat. The routed approver decides on the "
    "**Review & approval** tab, where the decision is recorded with their name and comment. The "
    "person who prepared a case cannot approve it."
)
_STEP_NAME = {"working_capital": "Funding need", "lendwise": "Lender comparison"}
_STAGE = {
    "onboarding": "Readiness",
    "working_capital": "Funding need",
    "lendwise": "Lender comparison",
    "critic": "Verification",
    "routing": "Routing",
    "approval": "Approval",
}
_STATUS = {
    "CREATED": "created; no stage has run yet",
    "IN_PROGRESS": "running",
    "PAUSED": "paused and waiting for input",
    "FAILED": "stopped with an error",
    "AWAITING_APPROVAL": "waiting for the routed decision-maker",
    "HELD": "held for a person to decide who takes the decision",
    "APPROVED": "decided in favour, internally; the MSME chooses its lender outside CredAssure",
    "REJECTED": "declined by the decision-maker",
    "RETURNED": "sent back to a stage by the decision-maker",
    "ABANDONED": "abandoned",
}
_NEXT = {
    "CREATED": "Upload the case files on Documents, then press Run on Workflow.",
    "PAUSED": "Answer the question card on Workflow and press Resume; only the blocked stage runs "
    "again.",
    "FAILED": "An evaluator can retry the failed stage; the error is in the stage tracker.",
    "AWAITING_APPROVAL": "The routed decision-maker reads the report and decides.",
    "HELD": "A person decides who takes the decision: the amount sits exactly on the threshold.",
    "RETURNED": "Fix what the decision-maker's comment asks for, then run that stage again.",
}
# Stage results in words: the Critic's banned list blocks gate tokens and approval wording even in
# code text (VER-03), so the status reply never uses them.
_DECISION = {"GO": "passed", "NO_GO": "stopped", "NEEDS_INPUT": "needs input", "ERROR": "error"}
_ROUTE = {
    "DIRECTOR_FINANCE": "Director, Finance",
    "director_finance": "Director, Finance",
    "VP_FINANCE": "VP, Finance",
    "vp_finance": "VP, Finance",
}
_SLOT = re.compile(r"\{([\w.\-]+)\}")


class ToolChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an echoed schema is invalid, never a choice
    tool: str
    query: str


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an echoed schema is invalid, never an answer
    abstain: bool
    answer: str


# Small models copy a concrete reply far better than a JSON schema (live qwen3:8b echoed it).
TOOL_EXAMPLES = (
    '{"tool": "search_regulations", "query": "CGTMSE annual guarantee fee basis"}',
    '{"tool": "get_case_facts", "query": ""}',
)
ANSWER_EXAMPLES = (
    '{"abstain": false, "answer": "The fee is charged on the guaranteed amount in the first '
    'year [2.3]. After that it is charged on the outstanding amount [2.4]."}',
    '{"abstain": true, "answer": ""}',
)


@dataclass(frozen=True)
class Reply:
    answer: str
    citations: tuple[dict[str, Any], ...] = ()  # cited passages, in order of first citation
    refused: bool = False
    refusal_code: str | None = None
    injection_flagged: bool = False
    ranking: tuple[str, ...] | None = None
    tool: str | None = None
    tool_valid: bool | None = None
    dropped: int = 0  # retrieved passages withheld by the injection scanner (BR-15)
    source: str = "code"  # model | code
    findings: tuple[str, ...] = field(default=())
    facts: tuple[str, ...] = ()  # ledger keys rendered as slots (lineage inputs)
    cut: int = 0  # answer sentences cut for lacking a valid span id (P5)
    span_ids: tuple[str, ...] = ()  # "n.m" spans cited by the kept sentences
    # CP-07: help, case_status, case_figures, blocker, regulatory, policy; SUP-02: data_correction,
    # approval_action
    intent: str | None = None
    routed_by: str | None = None  # code | model

    @property
    def abstained(self) -> bool:
        return self.answer == ABSTAIN


def version() -> str:
    return __version__


def _choose(llm: LLMPort, message: str, history: str, has_case: bool) -> tuple[str, str, bool]:
    """scope #20: the model picks a tool; code validates the name and the query. Without a case
    a case tool is invalid (CP-07): code falls back, it never opens case data."""
    prompt = registry()["cp_tool"].render(question=message, history=history)
    try:
        choice: ToolChoice | None = complete_model(
            llm, "cp_tool", ToolChoice, prompt, examples=TOOL_EXAMPLES
        )
    except LLMError:
        choice = None
    query = (choice.query if choice else "").strip()
    if (
        choice is not None
        and choice.tool in TOOLS
        and (has_case or choice.tool not in CASE_TOOLS)
        and (choice.tool in CASE_TOOLS or 1 <= len(query) <= 300)
    ):
        return choice.tool, query, True
    return DEFAULT_TOOL, message[:300], False


def _slot_values(facts: Mapping[str, Mapping[str, str]]) -> dict[str, str]:
    """Code-rendered display values for scalar facts (money, rates, weeks, ids)."""
    out: dict[str, str] = {}
    for key, f in facts.items():
        value, unit = str(f.get("value", "")), str(f.get("unit", ""))
        if unit == "json" or not value or "\n" in value:
            continue
        try:
            if unit == "INR":
                out[key] = slot_fmt.money(Decimal(value))
            elif unit == "rate":
                out[key] = slot_fmt.rate(Decimal(value))
            else:
                out[key] = value
        except InvalidOperation:
            continue
    return out


def _history(turns: Sequence[tuple[str, str]]) -> str:
    # A stored turn the scanner flags is never replayed to the model (BR-15, 9e security review).
    turns = [(role, text) for role, text in turns if not scan(text)]
    if not turns:
        return "(none)"
    lit = spotlight(turns)
    return f"{lit.preamble}\n{lit.text}"


def _abstain(tool: str | None, valid: bool | None, dropped: int = 0, *why: str) -> Reply:
    return Reply(ABSTAIN, tool=tool, tool_valid=valid, dropped=dropped, findings=tuple(why))


def _status_text(info: Mapping[str, Any]) -> str:
    """CP-10: the case's state in plain words, rendered by code from stored fields only."""
    status = str(info.get("status") or "CREATED")
    lines = [f"This case is {_STATUS.get(status, status.lower().replace('_', ' '))}."]
    stage = info.get("current_stage")
    if stage and status not in ("APPROVED", "REJECTED"):
        lines.append(f"Current stage: {_STAGE.get(str(stage), str(stage))}.")
    done = [
        f"{_STAGE.get(str(s['stage']), str(s['stage']))} "
        f"{_DECISION.get(str(s['decision']), str(s['decision']).lower())}"
        for s in info.get("stages") or []
        if s.get("decision")
    ]
    if done:
        lines.append("Stage results: " + ", ".join(done) + ".")
    route = info.get("route")
    if route:
        lines.append(f"Routed to: {_ROUTE.get(str(route), str(route).replace('_', ' ').title())}.")
    if info.get("blockers"):
        lines.append("Ask why it is blocked to see what to fix.")
    if info.get("report_stale"):
        lines.append("The report is stale: the preparer regenerates it before the decision.")
    nxt = _NEXT.get(status)
    if nxt:
        lines.append(f"Next: {nxt}")
    return "\n".join(lines)


def _code_reply(
    text: str, tool: str, route: "it.Route | None", case_id: str, tools: ToolPort
) -> Reply:
    """A code-written answer about the case still passes the Critic (R4) before anyone sees it."""
    if tools.call("verify_claims", case_id, {"text": text}):
        return Reply(
            ABSTAIN,
            tool=tool,
            tool_valid=True,
            findings=("critic",),
            intent=route.intent if route else None,
            routed_by=route.by if route else None,
        )
    return Reply(
        text,
        tool=tool,
        tool_valid=True,
        intent=route.intent if route else None,
        routed_by=route.by if route else None,
    )


def answer(
    message: str,
    *,
    case_id: str | None,
    tools: ToolPort,
    llm: LLMPort | None,
    history: Sequence[tuple[str, str]],
    offer_ids: Collection[str],
    as_of: date,
    progress: Callable[[str], None] | None = None,
) -> Reply:
    """One chat turn. ``message`` is already PII-redacted by the gateway (ONB-06). ``progress``
    receives stage names (routing, retrieving, drafting, checking) for the stream (CP-12); it never
    receives answer text, which leaves only after the Critic."""
    tick = progress or (lambda _stage: None)
    flagged = bool(scan(message))
    refusal = policy.check(message, case_id=case_id or "", offer_ids=offer_ids, as_of=as_of)
    if refusal is not None:
        return Reply(
            refusal.text,
            refused=refusal.refused,
            refusal_code=refusal.code,
            injection_flagged=flagged,
        )
    if flagged and case_id is None:  # BR-15, with nothing to show: a fixed reply
        return Reply(INJECTION_REPLY_NO_CASE, injection_flagged=True, refusal_code="INJECTION")
    if flagged and case_id is not None:  # BR-15: an instruction in chat changes nothing
        facts = tools.call("get_case_facts", case_id)
        raw = str(facts.get("lw.ranking", {}).get("value", ""))
        ranking = tuple(x for x in raw.split(",") if x and x != "none")
        text = INJECTION_REPLY.format(ranking=", ".join(ranking) or NO_RANKING)
        return Reply(text, injection_flagged=True, ranking=ranking, refusal_code="INJECTION")
    tick("routing")
    action = it.chat_action(message)  # SUP-02: not a question; nothing is changed from chat
    if action is not None:
        if action.intent == it.APPROVAL_ACTION:
            text = APPROVAL_REPLY
        elif action.clarify or action.file_kind is None:
            text = CORRECTION_CLARIFY
        else:
            text = CORRECTION_REPLY.format(
                form=FORM_NAME[action.file_kind], step=_STEP_NAME[action.reopen_stage or ""]
            )
        return Reply(text, intent=action.intent, routed_by="code")
    routed = it.route(message, has_case=case_id is not None)
    if case_id is None and (
        (routed is not None and routed.intent in it.CASE_INTENTS) or it.case_needed(message)
    ):
        return Reply(OPEN_CASE, intent=routed.intent if routed else it.STATUS, routed_by="code")
    if case_id is not None and routed is not None and routed.tool == "get_case_status":
        return _code_reply(
            _status_text(tools.call("get_case_status", case_id)),
            routed.tool,
            routed,
            case_id,
            tools,
        )
    if llm is None and not (routed is not None and routed.tool == "explain_blocker"):
        return _abstain(None, None, 0, "model off")  # ADR 0003 §2: no model, no free text

    past = _history(history)
    if routed is not None:
        tool, query, valid = routed.tool, message[:300], True
    elif llm is None:  # unreachable: only code-routed explain_blocker runs without the model
        return _abstain(None, None, 0, "model off")
    else:
        tool, query, valid = _choose(llm, message, past, case_id is not None)
        routed = it.Route(_intent_of(tool), tool, "model") if valid else None
    r_intent, r_by = (routed.intent, routed.by) if routed else (None, None)
    if tool in CASE_TOOLS and case_id is None:  # unreachable: CP-07 checks above; fail closed
        return replace(_abstain(tool, False, 0, "no case"), intent=r_intent, routed_by=r_by)
    if tool == "explain_blocker" and case_id is not None:
        info = tools.call("explain_blocker", case_id)
        lines = [f"{b['message']} {b.get('next_action') or ''}".strip() for b in info["blockers"]]
        if info.get("question"):
            lines.append(str(info["question"]))
        text = "\n".join(lines) or NO_BLOCKER
        if tools.call("verify_claims", case_id, {"text": text}):
            return Reply(
                ABSTAIN,
                tool=tool,
                tool_valid=valid,
                findings=("critic",),
                intent=r_intent,
                routed_by=r_by,
            )
        return Reply(text, tool=tool, tool_valid=valid, intent=r_intent, routed_by=r_by)
    if tool == "get_case_status" and case_id is not None:
        return _code_reply(
            _status_text(tools.call("get_case_status", case_id)), tool, routed, case_id, tools
        )
    if llm is None:  # pragma: no cover - guarded above; kept for the type checker
        return replace(_abstain(tool, valid, 0, "model off"), intent=r_intent, routed_by=r_by)

    values: dict[str, str] = {}
    passages: list[dict[str, Any]] = []
    dropped = 0
    tick("retrieving")
    if tool == "get_case_facts" and case_id is not None:
        values = _slot_values(tools.call("get_case_facts", case_id))
        if not values:
            return replace(
                _abstain(tool, valid, 0, "no case facts"), intent=r_intent, routed_by=r_by
            )
    else:
        # The question's own words stay in the search: a small model's rewrite drops terms
        # ("at the latest", "45 days") that the passages use (live qwen3:8b, T011).
        search = message if query.lower() in message.lower() else f"{message} {query}"
        try:
            found = tools.call(tool, case_id or "", {"query": search[:600]})
        except Exception:  # vector store or embedder down: fail closed to the abstention (Q5)
            return replace(
                _abstain(tool, valid, 0, "search unavailable"), intent=r_intent, routed_by=r_by
            )
        for p in found:
            if p["injection_flag"] or scan(f"{p.get('section_path') or ''}\n{p['text']}"):
                dropped += 1
                continue
            passages.append(p)
        passages = passages[:MAX_PASSAGES]
        if not passages:
            return replace(
                _abstain(tool, valid, dropped, "no passages"), intent=r_intent, routed_by=r_by
            )

    numbered = {
        n: spans.number(n, str(p.get("section_path") or ""), str(p["text"]))
        for n, p in enumerate(passages, start=1)
    }
    lit = spotlight(
        [(p["chunk_id"], numbered[n].text) for n, p in enumerate(passages, start=1)],
        cite_as="[n.m], the passage and sentence number",
    )
    prompt = registry()["cp_answer"].render(
        question=message,
        history=past,
        preamble=lit.preamble if passages else "",
        passages=lit.text if passages else "(none)",
        slots="\n".join(sorted(values)) or "(none)",
    )
    tick("drafting")
    try:
        draft = complete_model(llm, "cp_answer", Draft, prompt, examples=ANSWER_EXAMPLES)
    except LLMError:
        return replace(
            _abstain(tool, valid, dropped, "model error"), intent=r_intent, routed_by=r_by
        )
    if draft.abstain or not draft.answer.strip() or ABSTAIN in draft.answer:
        return replace(
            _abstain(tool, valid, dropped, "model abstained"), intent=r_intent, routed_by=r_by
        )

    kept = spans.cut(
        draft.answer.strip(),
        {n: s.spans for n, s in numbered.items()},
        lit.source_map,
        values,
    )
    if not kept.kept:  # every sentence lacked a valid span id or used an unknown slot
        return replace(
            _abstain(tool, valid, dropped, f"no supported sentence (cut {kept.cut})"),
            intent=r_intent,
            routed_by=r_by,
        )
    used = {k: values[k] for k in kept.slots}
    text = _SLOT.sub(lambda m: values[m.group(1)], kept.text)
    if (passages and not kept.cited) or (not passages and not used):
        return replace(
            _abstain(tool, valid, dropped, "nothing cited"), intent=r_intent, routed_by=r_by
        )
    tick("checking")
    findings = tools.call(
        "verify_claims", case_id or "", {"text": text, "slots": used, "model": True}
    )
    if findings:
        return replace(
            _abstain(tool, valid, dropped, *(f.code.value for f in findings)),
            intent=r_intent,
            routed_by=r_by,
        )
    meta = ("chunk_id", "doc_id", "title", "section_path", "effective_from", "collection", "href")
    return Reply(
        text,
        citations=tuple(
            {k: passages[n - 1].get(k) for k in meta}
            | {"span_ids": [i for i in kept.span_ids if i.split(".")[0] == str(n)]}
            for n in kept.cited
        ),
        tool=tool,
        tool_valid=valid,
        dropped=dropped,
        source="model",
        facts=tuple(used),
        cut=kept.cut,
        span_ids=kept.span_ids,
        intent=r_intent,
        routed_by=r_by,
    )


def _intent_of(tool: str) -> str:
    return next(i for i, t in it.TOOL_FOR.items() if t == tool)
