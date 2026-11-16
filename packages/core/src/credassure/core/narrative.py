"""Narrative drafting under the Critic (scope #21, VER-05) and its ledger record.

Every stage narrative is checked by the Critic. With findings, the next draft uses the
``regenerate`` prompt (the agent's own prompt plus the findings); after the last regeneration the
Supervisor sets ``template_only`` and the agent's code template is used. The text, its source and
the code-rendered slot values go to the ledger as ``<prefix>narrative`` so the Critic stage can
re-verify them against the current ledger (BR-05).
"""

import json
from collections.abc import Mapping

from credassure.core.errors import LLMError
from credassure.core.ports import StageContext
from credassure.core.prompts import registry

REGENERATE = "regenerate"


def draft(ctx: StageContext, name: str, prompt: str) -> tuple[str | None, str | None]:
    """(model reply, prompt name used); reply None means: use the template."""
    if ctx.llm is None or ctx.template_only:
        return None, None
    if ctx.findings:
        lines = "\n".join(f"- {f.code.value}: {f.message}" for f in ctx.findings)
        prompt, name = registry()[REGENERATE].render(original=prompt, findings=lines), REGENERATE
    try:
        return ctx.llm.complete(prompt, name=name).strip(), name
    except LLMError:  # slow or down model: the gate is decided, only wording is lost
        return None, name


def record(
    ctx: StageContext,
    prefix: str,
    text: str,
    *,
    model: bool,
    slots: Mapping[str, str],
    source_ref: str,
    produced_by: str,
    input_hash: str | None = None,
) -> None:
    value = json.dumps(
        {"source": "model" if model else "template", "slots": dict(slots), "text": text},
        sort_keys=True,
        ensure_ascii=False,
    )
    ctx.ledger.put_fact(
        ctx.case_id,
        f"{prefix}narrative",
        value,
        unit="json",
        source_type="narrative",
        source_ref=source_ref,
        produced_by=produced_by,
        input_hash=input_hash,
    )


def parse(value: str | None) -> tuple[str, bool, dict[str, str]] | None:
    """(text, model?, slots) from a stored ``<prefix>narrative`` fact."""
    if not value:
        return None
    data = json.loads(value)
    return (
        str(data["text"]),
        data["source"] == "model",
        {str(k): str(v) for k, v in data["slots"].items()},
    )
