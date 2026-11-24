"""Plain-language explanation of blockers and next actions (BRD ONB-04).

Code always writes a template explanation from the rule results. If a model endpoint is
configured, the model may only REWORD it. The rewording is kept only if the guard confirms
it adds no number or date, names every failed rule, and does not contradict the decision.
Otherwise the template is shown. The gate never depends on the model, and the model never
sees the user's own words.

Settings (any OpenAI-compatible chat endpoint):
    CREDASSURE_LLM_BASE_URL   course Qwen: https://<host>:<port>/v1   local Ollama: http://localhost:11434/v1
    CREDASSURE_LLM_MODEL      course: Qwen/Qwen3-8B                   Ollama: qwen3:8b
    CREDASSURE_LLM_API_KEY    the group's key (Ollama ignores it)
    CREDASSURE_LLM_CA_CERT    path to the group's .crt file (course endpoint only)
    CREDASSURE_LLM_TIMEOUT    seconds per call (default 60; a local model's first call loads it)
    CREDASSURE_LLM_ATTEMPTS   rewordings tried before the template is used (default 2)
    CREDASSURE_LLM_BACKOFF    waits before retrying a 429/503, in seconds (default "2,4")
    CREDASSURE_LLM_NO_THINK   "auto" (default: on for Qwen models), "1" or "0"
    CREDASSURE_LLM_EXTRA_BODY optional JSON added to each request,
                              e.g. {"chat_template_kwargs": {"enable_thinking": false}}
"""
from __future__ import annotations

import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

from .schemas import CheckOutcome, Decision, StageResult

LLMFn = Callable[[str, str], str]   # (system_prompt, user_prompt) -> text
THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_ONE_AT_A_TIME = threading.Lock()     # the course key allows one active request per group

PROMPT_VERSION = "onboarding-explain-v2"   # bump whenever SYSTEM_PROMPT or the user prompt changes

SYSTEM_PROMPT = (
    "You explain a loan-proposal readiness check to an employee in plain, friendly English. "
    "Use ONLY the facts given. Do not add, change or round any date, number, course name or ID. "
    "Do not change the decision. Mention every blocker. Do not give advice beyond the next action given. "
    "Write 2 to 4 short sentences, no lists, no headings."
)

_HEADLINE = {
    Decision.GO: "You're cleared to prepare this loan proposal.",
    Decision.NO_GO: "You can't prepare this loan proposal yet.",
    Decision.NEEDS_INPUT: "We couldn't confirm your readiness from the HR records.",
    Decision.ERROR: "The readiness check could not run.",
}


def template_explanation(result: StageResult) -> str:
    parts = [_HEADLINE[result.decision]]
    bad = [c for c in result.checks if c.outcome != CheckOutcome.PASS]
    parts += [c.detail for c in bad]
    parts += result.warnings
    parts.append(result.next_action)
    return " ".join(parts)


_NUM = re.compile(r"\d[\d\-/.,:]*\d|\d")


def guard_explanation(text: str, result: StageResult, template: str) -> tuple[bool, str]:
    if not text or len(text.split()) > 150:
        return False, "empty or too long"
    allowed = set(_NUM.findall(template))
    extra = [n for n in _NUM.findall(text) if n not in allowed]
    if extra:
        return False, f"introduced numbers/dates not in facts: {extra}"
    low = text.lower()
    for c in result.checks:
        if c.outcome == CheckOutcome.PASS:
            continue
        m = re.search(r"'([^']+)'", c.detail)
        key = (m.group(1) if m else c.check_id).lower()
        if key not in low:
            return False, f"blocker not mentioned: {key}"
    if result.decision != Decision.GO and re.search(r"\b(you are|you're) (cleared|qualified|ready)\b", low):
        return False, "contradicts decision"
    return True, "ok"


def _strip_thinking(text: str) -> str:
    """Remove Qwen3 reasoning: <think>...</think> blocks, or an unclosed <think> at the start."""
    text = THINK_BLOCK.sub("", text or "")
    if "<think>" in text:                       # cut off mid-thought: nothing usable after it
        text = text.split("<think>")[0]
    return text.strip()


def _retry_waits() -> list[float]:
    """Seconds to wait before each retry on 429/5xx (BRD NFR-04: at most two retries)."""
    raw = os.getenv("CREDASSURE_LLM_BACKOFF", "2,4")
    return [float(x) for x in raw.split(",") if x.strip()][:2]


def openai_compatible_llm() -> Optional[LLMFn]:
    """A client for any OpenAI-compatible chat endpoint, or None if none is configured."""
    base, key, model = (os.getenv("CREDASSURE_LLM_BASE_URL"), os.getenv("CREDASSURE_LLM_API_KEY"),
                        os.getenv("CREDASSURE_LLM_MODEL"))
    if not (base and model):
        return None
    timeout = float(os.getenv("CREDASSURE_LLM_TIMEOUT", "60"))
    no_think = os.getenv("CREDASSURE_LLM_NO_THINK", "auto").lower()
    no_think = ("qwen" in model.lower()) if no_think == "auto" else no_think in ("1", "true", "yes")
    extra = json.loads(os.getenv("CREDASSURE_LLM_EXTRA_BODY", "{}") or "{}")

    handlers = []
    cafile = os.getenv("CREDASSURE_LLM_CA_CERT")
    if cafile:                                   # the course endpoint uses its own certificate authority
        if not os.path.exists(cafile):
            raise FileNotFoundError(f"CREDASSURE_LLM_CA_CERT not found: {cafile}")
        handlers.append(urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=cafile)))
    if any(h in base for h in ("localhost", "127.0.0.1", "host.docker.internal")):
        handlers.append(urllib.request.ProxyHandler({}))   # never send local traffic through a proxy
    opener = urllib.request.build_opener(*handlers)

    def call(system: str, user: str) -> str:
        payload = {"model": model, "temperature": 0, "max_tokens": 220,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user + (" /no_think" if no_think else "")}],
                   **extra}
        data = json.dumps(payload).encode()
        waits = _retry_waits()
        for attempt in range(len(waits) + 1):
            req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=data,
                                         headers={"Content-Type": "application/json",
                                                  "Authorization": f"Bearer {key or 'none'}"})
            try:
                with _ONE_AT_A_TIME, opener.open(req, timeout=timeout) as resp:
                    body = json.loads(resp.read())
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 500, 502, 503, 504) and attempt < len(waits):   # busy: wait, retry
                    time.sleep(waits[attempt])
                    continue
                raise                                # 400/401/404 are configuration errors: no retry
        msg = body["choices"][0]["message"]
        return _strip_thinking(msg.get("content") or "")
    return call


def user_prompt(result: StageResult, template: str) -> str:
    return (f"Decision: {result.decision.value}\nFacts:\n{template}\n\n"
            "Rewrite these facts as a short, friendly explanation for the employee.")


def explain(result: StageResult, llm: Optional[LLMFn] = None) -> StageResult:
    """Template always; LLM rewrite only if it passes the guard. Never raises."""
    template = template_explanation(result)
    result.explanation, result.explanation_source = template, "template"
    if llm is None:
        try:
            llm = openai_compatible_llm()
        except Exception as exc:      # bad settings (e.g. certificate path) must never break the gate
            result.warnings.append(f"LLM settings problem ({exc}); template used.")
            return result
    if llm is None:
        return result
    attempts = max(1, int(os.getenv("CREDASSURE_LLM_ATTEMPTS", "2")))
    problem = ""
    for _ in range(attempts):
        try:
            text = llm(SYSTEM_PROMPT, user_prompt(result, template))
        except Exception as exc:  # endpoint down, quota, timeout, bad JSON: the client already retried
            result.warnings.append(f"LLM explanation unavailable ({type(exc).__name__}); template used.")
            return result
        ok, why = guard_explanation(text, result, template)
        if ok:
            result.explanation, result.explanation_source = text, "llm"
            return result
        problem = f"rejected ({why})"
    result.warnings.append(f"LLM explanation {problem} after {attempts} attempt(s); template used.")
    return result
