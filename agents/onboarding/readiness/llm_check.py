"""Check that the model endpoint works before running the agent with it.

    python -m readiness.llm_check

1. Shows which endpoint and model are configured.
2. Sends a one-word test message and reports the time taken.
3. Runs one real explanation (preparer EMP-014, three blockers) and shows whether
   the guard accepted the model's wording or fell back to the template.
Nothing is written to the case database or the audit log.
"""
from __future__ import annotations

import os
import sys
import time

from . import generate_hr_data as gen
from .checker import evaluate_readiness
from .explain import PROMPT_VERSION, explain, openai_compatible_llm, template_explanation
from .tools import get_employee_record, get_policy_acknowledgements, get_training_status


def _hint(exc: Exception, model: str) -> str:
    text = str(exc)
    if "401" in text or "403" in text:
        return "The key was refused: check CREDASSURE_LLM_API_KEY (your group's key, no spaces)."
    if "404" in text:
        return f"Not found: check the URL ends in /v1 and the model name is exactly {model}."
    if "CERTIFICATE" in text.upper() or "SSL" in text.upper():
        return "Certificate problem: set CREDASSURE_LLM_CA_CERT to your group's .crt file."
    if "429" in text or "503" in text:
        return "The endpoint is busy (one request at a time per group). Wait a little and try again."
    return ("Is the model server running? For Ollama: open the Ollama app or run 'ollama serve', and check\n"
            f"that 'ollama list' shows {model}. For the course endpoint: check the URL and that you are online.")


def main() -> int:
    base, model = os.getenv("CREDASSURE_LLM_BASE_URL"), os.getenv("CREDASSURE_LLM_MODEL")
    print(f"Endpoint : {base or '(not set)'}")
    print(f"Model    : {model or '(not set)'}")
    print(f"Prompt   : {PROMPT_VERSION}")
    print(f"CA cert  : {os.getenv('CREDASSURE_LLM_CA_CERT') or '(none: fine for Ollama)'}")
    try:
        llm = openai_compatible_llm()
    except FileNotFoundError as exc:
        print(f"\nFAILED: {exc}\nCheck the certificate path in your setup script.")
        return 2
    if llm is None:
        print("\nNo model configured, so the agent will use template explanations (this is fine).\n"
              "Local Qwen3 8B on Ollama:   . .\\scripts\\use_ollama_qwen.ps1\n"
              "Course Qwen3-8B endpoint:   . .\\scripts\\use_course_qwen.ps1")
        return 1

    print("\n[1/2] Test message ...", flush=True)
    t0 = time.time()
    try:
        reply = llm("Reply with exactly one word.", "Say OK.")
    except Exception as exc:
        print(f"FAILED: {type(exc).__name__}: {exc}\n" + _hint(exc, model))
        return 2
    print(f"OK in {time.time() - t0:.1f}s, reply: {reply[:60]!r}")

    print("\n[2/2] Sample explanation for EMP-014 (three blockers) ...", flush=True)
    gen.ensure_hr_store()
    emp = get_employee_record("EMP-014")
    result = evaluate_readiness("CASE-LLM-CHECK", emp, get_training_status("EMP-014"), gen.AS_OF,
                                acknowledgements=get_policy_acknowledgements("EMP-014"))
    template = template_explanation(result)
    t0 = time.time()
    result = explain(result)
    print(f"Done in {time.time() - t0:.1f}s. Source used: {result.explanation_source.upper()}")
    print(f"\nTemplate text:\n  {template}")
    print(f"\nShown to the preparer:\n  {result.explanation}")
    for w in result.warnings:
        print(f"\nNote: {w}")
    print(f"\nDecision (always from code): {result.decision.value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
