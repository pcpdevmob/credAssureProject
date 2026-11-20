"""CP-07 intent routing in code (ADR 0035). Runs after the refusal policy, before any model call.

Code routes a question when its wording is unambiguous; otherwise it returns None and the model
picks a tool from the fixed list (scope #20), which code still validates. The model can never pick a
case tool without a case, and code never routes a question that names a regulator, scheme or tax to
product help: those stay on the cited regulatory path the frozen evaluation measures.
"""

import re
from dataclasses import dataclass

HELP, STATUS, FIGURES, BLOCKER, REGULATORY, POLICY = (
    "help",
    "case_status",
    "case_figures",
    "blocker",
    "regulatory",
    "policy",
)
INTENTS = (HELP, STATUS, FIGURES, BLOCKER, REGULATORY, POLICY)
TOOL_FOR = {
    HELP: "search_help",
    STATUS: "get_case_status",
    FIGURES: "get_case_facts",
    BLOCKER: "explain_blocker",
    REGULATORY: "search_regulations",
    POLICY: "search_policies",
}
CASE_INTENTS = frozenset({STATUS, FIGURES, BLOCKER})

# Words that tie a question to the outside rulebook. Any of them keeps the question off `help`.
_REGULATORY = re.compile(
    r"\b(?:rbi|reserve bank|master direction|cgtmse|cgs|gst|cgst|msmed|msme act|udyam|treds|"
    r"income[- ]tax|section \d|s\.\s?\d|43b|37\(2\)|ebl?r|mclr|repo rate|sidbi|mudra|dpdp act|"
    r"gazette|notification|circular|samadhaan|priority sector|kfs format|annex)\b",
    re.IGNORECASE,
)
_POLICY = re.compile(
    r"\b(?:our|company|internal|wc-pol|working[- ]capital policy|approval matrix|delegation|"
    r"negotiation conduct|data[- ]handling policy|training catalogue)\b"
    r"[^\n]{0,200}?\bpolic(?:y|ies)\b|"
    r"\b(?:wc-pol|approval matrix|delegation of authority)\b",
    re.IGNORECASE,
)
# The product itself: screens, buttons, roles, how-to, and how the AI and data are handled.
_HELP = re.compile(
    r"\b(?:credassure|ask credassure|copilot|this app|the app|screen|tab|button|page|menu|"
    r"dashboard|inbox|help centre|upload|re-?upload|log ?in|sign ?in|password|mfa|session|"
    r"acting role|role|preparer|approver|evaluator|workflow|stage tracker|live progress|"
    r"report version|regenerate|export|audit log|safety panel|attest\w*|citation|"
    r"ai[- ]generated|guardrail\w*|responsible ai|pii|personal (?:data|identifiers?)|aadhaar|"
    r"redact\w*|privacy|my data|data (?:protection|handling|stored|kept)|hallucinat\w*|"
    r"prompt injection|injection|does the ai|did the ai|is the ai|who decides|human in the loop|"
    r"errors?|"
    r"error message|problem\+json|request id|troubleshoot\w*|glossary|excel|template|"
    r"case[- ]authoring|json|csv)\b",
    re.IGNORECASE,
)
_HOW = re.compile(
    r"^\s*(?:how (?:do|can|should) (?:i|we)|where (?:do|can|is|are)|"
    r"what (?:does|is) the [^\n]{0,120}?"
    r"(?:button|tab|screen|page)|can i|why can'?t i|what happens (?:if|when))\b",
    re.IGNORECASE,
)
# Questions about the open case. A pronoun or "this case" is required for figures, so a general
# "what is APR?" stays regulatory.
_THIS_CASE = re.compile(
    r"\b(?:this|my|our|the current|current) (?:case|proposal|loan)\b|\bfor us\b", re.I
)
_STATUS = re.compile(
    r"\b(?:status|where (?:is|are) (?:we|it|this|my)|which stage|what stage|progress|"
    r"what(?:'s| is) next|next step|who (?:approves|will approve|decides)|routed|route|"
    r"is (?:it|this|my case) (?:approved|ready|done)|stale)\b",
    re.IGNORECASE,
)
_BLOCKER = re.compile(
    r"\b(?:blocked|blocker|paused|stuck|why (?:did|does|is) [^\n]{0,200}?(?:stop|fail|pause)|"
    r"what (?:do i|should i) (?:fix|upload)|needs? input|no[- ]go|failed)\b",
    re.IGNORECASE,
)
_FIGURES = re.compile(
    r"\b(?:funding need|recommended (?:amount|facility)|peak shortfall|shortfall|buffer|"
    r"apr|total cost|ranking|ranked|rank|cheapest|amount received|instalment|emi|bridge|"
    r"how much)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Route:
    intent: str
    tool: str
    by: str = "code"  # code | model


def route(message: str, *, has_case: bool) -> Route | None:
    """The intent code is sure of, or None (the model then picks a tool; code validates it)."""
    regulatory = bool(_REGULATORY.search(message))
    policy = bool(_POLICY.search(message))
    if policy and not _THIS_CASE.search(message):  # "who approves ... under our approval matrix"
        return Route(POLICY, TOOL_FOR[POLICY])
    if has_case:
        if _BLOCKER.search(message) and not regulatory:
            return Route(BLOCKER, TOOL_FOR[BLOCKER])
        if _THIS_CASE.search(message) or not regulatory:
            if _STATUS.search(message) and not _FIGURES.search(message):
                return Route(STATUS, TOOL_FOR[STATUS])
            if _THIS_CASE.search(message) and _FIGURES.search(message):
                return Route(FIGURES, TOOL_FOR[FIGURES])
    if regulatory:
        return Route(REGULATORY, TOOL_FOR[REGULATORY])
    if policy:
        return Route(POLICY, TOOL_FOR[POLICY])
    if _HELP.search(message) or _HOW.search(message):
        return Route(HELP, TOOL_FOR[HELP])
    return None


def case_needed(message: str) -> bool:
    """True when a question without an open case is about a case (status, blockers, figures)."""
    return bool(
        _THIS_CASE.search(message)
        and (_STATUS.search(message) or _BLOCKER.search(message) or _FIGURES.search(message))
    )
