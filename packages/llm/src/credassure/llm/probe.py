"""`make llm-probe`: does the configured endpoint honour guided JSON (response_format)?

Sends one tiny schema-bound request with guided decoding on and reports whether a valid reply
came back within the repair budget. Run it against Ollama and the course endpoint before setting
LLM_SUPPORTS_GUIDED_JSON=true (ADR 0017, PROGRESS open question). Never part of make check.
"""

import os
import ssl

import httpx2
from pydantic import BaseModel

from credassure.llm.client import OpenAICompatLLM
from credassure.llm.structured import StructuredOutputError, complete_model


class _Probe(BaseModel):
    stage: str
    weeks: int


def main() -> int:
    ca = os.environ.get("LLM_CA_CERT")
    llm = OpenAICompatLLM(
        os.environ["LLM_BASE_URL"],
        os.environ.get("LLM_API_KEY"),
        os.environ.get("LLM_MODEL", "default"),
        guided_json=True,
        max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "1024")),
        disable_thinking=os.environ.get("LLM_DISABLE_THINKING", "").lower() == "true",
        thinking_switch=(
            "reasoning_effort"
            if os.environ.get("LLM_THINKING_SWITCH") == "reasoning_effort"
            else "chat_template_kwargs"
        ),
        http_client=httpx2.Client(verify=ssl.create_default_context(cafile=ca)) if ca else None,
    )
    try:
        got = complete_model(
            llm, "llm_probe", _Probe, 'Reply with stage "working_capital", weeks 26.'
        )
    except StructuredOutputError:
        print("guided JSON: FAILED after 2 repairs; keep LLM_SUPPORTS_GUIDED_JSON=false")
        return 1
    print(f"guided JSON: OK {got.model_dump()}; LLM_SUPPORTS_GUIDED_JSON=true is safe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
