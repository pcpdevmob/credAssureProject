"""Ask CredAssure (CP-01..03, scope #2, #20, design-detail §2.4.6). On demand, never a stage.

    refusal policy (code) → injection check on the message (code) → model off? abstain →
    the model picks one of 4 fixed tools (code validates; invalid → search_regulations) →
    ≤5 passages, injection-scanned, split into numbered sentence spans [n.m] and spotlighted →
    the model answers citing a span after every sentence and writing case figures only as
    {fact.key} slots → code cuts every sentence without a valid span id (P5, scope #64), maps
    span ids to [chunk_id] and renders the slots → the Critic (verify_claims) → the answer, or
    exactly ABSTAIN when nothing is left.

case_id comes from the gateway, never from the model (SUP-08). The model never sees a figure it
could copy into an answer: case figures exist only as slot names, filled in by code.
"""

import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict

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

TOOLS = ("search_regulations", "search_policies", "get_case_facts", "explain_blocker")
DEFAULT_TOOL = "search_regulations"
MAX_PASSAGES = 5
INJECTION_REPLY = (
    "That message tries to change how the copilot works, so it was not followed. The offer "
    "ranking is set by code from the verified APR and cash-flow fit: {ranking}."
)
NO_RANKING = "no ranking has been calculated for this case yet"
NO_BLOCKER = "Nothing is blocked on this case right now."
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

    @property
    def abstained(self) -> bool:
        return self.answer == ABSTAIN


def version() -> str:
    return __version__


def _choose(llm: LLMPort, message: str, history: str) -> tuple[str, str, bool]:
    """scope #20: the model picks a tool; code validates the name and the query."""
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
        and (choice.tool in ("get_case_facts", "explain_blocker") or 1 <= len(query) <= 300)
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


def answer(
    message: str,
    *,
    case_id: str,
    tools: ToolPort,
    llm: LLMPort | None,
    history: Sequence[tuple[str, str]],
    offer_ids: Collection[str],
    as_of: date,
) -> Reply:
    """One chat turn. ``message`` is already PII-redacted by the gateway (ONB-06)."""
    flagged = bool(scan(message))
    refusal = policy.check(message, case_id=case_id, offer_ids=offer_ids, as_of=as_of)
    if refusal is not None:
        return Reply(
            refusal.text,
            refused=refusal.refused,
            refusal_code=refusal.code,
            injection_flagged=flagged,
        )
    if flagged:  # BR-15: an instruction in chat changes nothing; the code ranking stands
        facts = tools.call("get_case_facts", case_id)
        raw = str(facts.get("lw.ranking", {}).get("value", ""))
        ranking = tuple(x for x in raw.split(",") if x and x != "none")
        text = INJECTION_REPLY.format(ranking=", ".join(ranking) or NO_RANKING)
        return Reply(text, injection_flagged=True, ranking=ranking, refusal_code="INJECTION")
    if llm is None:  # ADR 0003 §2: no model, no free-text answer
        return _abstain(None, None, 0, "model off")

    past = _history(history)
    tool, query, valid = _choose(llm, message, past)
    if tool == "explain_blocker":
        info = tools.call("explain_blocker", case_id)
        lines = [f"{b['message']} {b.get('next_action') or ''}".strip() for b in info["blockers"]]
        if info.get("question"):
            lines.append(str(info["question"]))
        text = "\n".join(lines) or NO_BLOCKER
        if tools.call("verify_claims", case_id, {"text": text}):
            return _abstain(tool, valid, 0, "critic")
        return Reply(text, tool=tool, tool_valid=valid)

    values: dict[str, str] = {}
    passages: list[dict[str, Any]] = []
    dropped = 0
    if tool == "get_case_facts":
        values = _slot_values(tools.call("get_case_facts", case_id))
        if not values:
            return _abstain(tool, valid, 0, "no case facts")
    else:
        # The question's own words stay in the search: a small model's rewrite drops terms
        # ("at the latest", "45 days") that the passages use (live qwen3:8b, T011).
        search = message if query.lower() in message.lower() else f"{message} {query}"
        try:
            found = tools.call(tool, case_id, {"query": search[:600]})
        except Exception:  # vector store or embedder down: fail closed to the abstention (Q5)
            return _abstain(tool, valid, 0, "search unavailable")
        for p in found:
            if p["injection_flag"] or scan(f"{p.get('section_path') or ''}\n{p['text']}"):
                dropped += 1
                continue
            passages.append(p)
        passages = passages[:MAX_PASSAGES]
        if not passages:
            return _abstain(tool, valid, dropped, "no passages")

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
    try:
        draft = complete_model(llm, "cp_answer", Draft, prompt, examples=ANSWER_EXAMPLES)
    except LLMError:
        return _abstain(tool, valid, dropped, "model error")
    if draft.abstain or not draft.answer.strip() or ABSTAIN in draft.answer:
        return _abstain(tool, valid, dropped, "model abstained")

    kept = spans.cut(
        draft.answer.strip(),
        {n: s.spans for n, s in numbered.items()},
        lit.source_map,
        values,
    )
    if not kept.kept:  # every sentence lacked a valid span id or used an unknown slot
        return _abstain(tool, valid, dropped, f"no supported sentence (cut {kept.cut})")
    used = {k: values[k] for k in kept.slots}
    text = _SLOT.sub(lambda m: values[m.group(1)], kept.text)
    if (passages and not kept.cited) or (not passages and not used):
        return _abstain(tool, valid, dropped, "nothing cited")
    findings = tools.call("verify_claims", case_id, {"text": text, "slots": used, "model": True})
    if findings:
        return _abstain(tool, valid, dropped, *(f.code.value for f in findings))
    meta = ("chunk_id", "doc_id", "title", "section_path", "effective_from", "collection")
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
    )
