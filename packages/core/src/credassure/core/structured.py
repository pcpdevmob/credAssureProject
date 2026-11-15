"""Structured output (ARCHITECTURE §8.6): schema and examples in the prompt, Pydantic validation,
repair at most twice, then StructuredOutputError. The schema is also passed to the client, which
sends it as guided decoding when LLM_SUPPORTS_GUIDED_JSON=true.
"""

import json
import re
from collections.abc import Sequence

from pydantic import BaseModel, ValidationError

from credassure.core.errors import LLMError
from credassure.core.ports import LLMPort

MAX_REPAIRS = 2
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class StructuredOutputError(LLMError):
    """The model did not return valid JSON for the schema after two repairs."""


def _unfence(text: str) -> str:
    m = _FENCE.match(text)
    return m.group(1) if m else text.strip()


def complete_model[T: BaseModel](
    llm: LLMPort, name: str, schema: type[T], prompt: str, *, examples: Sequence[str] = ()
) -> T:
    js = schema.model_json_schema()
    base = f"{prompt}\n\nReturn only JSON that matches this schema:\n{json.dumps(js)}"
    if examples:
        base += "\n\nExamples:\n" + "\n".join(examples)
    ask = base
    for _ in range(MAX_REPAIRS + 1):
        text = llm.complete(ask, name=name, json_schema=js)
        try:
            return schema.model_validate_json(_unfence(text))
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(map(str, e['loc'])) or 'root'}: {e['msg']}" for e in exc.errors()[:5]
            )
            ask = (
                f"{base}\n\nYour previous reply was invalid ({problems}).\n"
                f"Previous reply:\n{text[:2000]}\n\nReturn the corrected JSON only."
            )
    raise StructuredOutputError(f"{name}: no valid JSON after {MAX_REPAIRS} repairs")
