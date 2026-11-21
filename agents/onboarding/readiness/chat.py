"""Handles a chat message the Supervisor routes to the Onboarding Agent (BRD ONB-04, ONB-06).

1. Redact Aadhaar, PAN and bank account numbers first. The raw message is never passed on,
   logged or stored; if anything was removed, the reply says so and why.
2. If the message is about readiness ("am I cleared?", "why am I blocked?"), run the gate
   and reply with its plain-language explanation.
3. Anything else goes back to the Supervisor's routing: policy questions belong to the
   Ask CredAssure copilot. This agent answers only about onboarding readiness.

The model never sees the user's message: it only rewords text the rules wrote.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

from .audit import audit_event
from .explain import LLMFn
from .gate import run_readiness_gate
from .pii import redact, refusal_message
from .schemas import StageResult

READINESS_WORDS = re.compile(
    r"(?i)\b(cleared?|ready|readiness|blocked|blockers?|why can'?t|qualif\w*|eligible|allowed|"
    r"go|no-go|training|acknowledg\w*|onboarding|prepare|proposal|status|pending|missing)\b")
OUT_OF_SCOPE = ("I can only help with your onboarding readiness here. For policy or regulatory "
                "questions, ask the CredAssure copilot.")


def handle_message(case_id: str, employee_id: str, message: str, as_of: Optional[date] = None,
                   llm: Optional[LLMFn] = None) -> dict:
    clean, kinds = redact(message or "")
    parts: list[str] = []
    if kinds:
        parts.append(refusal_message(kinds))

    result: Optional[StageResult] = None
    intent = "readiness" if READINESS_WORDS.search(clean) else ("pii_only" if kinds else "out_of_scope")
    if intent == "readiness":
        result = run_readiness_gate(case_id, employee_id, as_of=as_of, llm=llm)
        parts.append(result.explanation)
    elif intent == "out_of_scope":
        parts.append(OUT_OF_SCOPE)

    audit_event(case_id, actor_role="onboarding_agent", action="onboarding_message",
                status=intent, details={"employee_id": employee_id, "pii_redacted": kinds,
                                        "message_redacted": clean})
    return {"case_id": case_id, "employee_id": employee_id, "intent": intent, "pii_redacted": kinds,
            "message_redacted": clean, "reply": " ".join(parts), "readiness": result}
