"""Langfuse span export behind TRACING_ENABLED, with the PII mask (ARCHITECTURE §8.8, NFR-07).

Spans are created by `credassure.observability.tracing.span`; this module only installs a sink.
Every string is redacted before it leaves the process, and an export failure is logged and
swallowed: tracing off, missing keys or a failing tracer never break a request.
"""

import logging
from collections.abc import Callable
from typing import Any

from credassure.gateway.settings import Settings
from credassure.observability.tracing import set_exporter
from credassure.security.pii import redact_value

_log = logging.getLogger("credassure.tracing")


def mask(data: Any, **_: Any) -> Any:
    """Recursive PII redaction; also Langfuse's `mask` hook (called as mask(data=...))."""
    return redact_value(data)


def gen_ai_attributes(name: str, attrs: dict[str, Any], model: str | None) -> dict[str, Any]:
    """OpenTelemetry GenAI semantic-convention keys for a model span (ADR 0029 R5)."""
    if name != "llm":
        return {}
    out: dict[str, Any] = {"gen_ai.operation.name": "chat", "gen_ai.system": "openai_compatible"}
    if model:
        out["gen_ai.request.model"] = model
    for ours, theirs in (
        ("prompt_tokens", "gen_ai.usage.input_tokens"),
        ("completion_tokens", "gen_ai.usage.output_tokens"),
        ("prompt", "credassure.prompt.name"),
        ("prompt_version", "credassure.prompt.version"),
    ):
        if attrs.get(ours) is not None:
            out[theirs] = attrs[ours]
    return out


def make_exporter(client: Any, model: str | None = None) -> Callable[[str, dict[str, Any]], None]:
    def export(name: str, attrs: dict[str, Any]) -> None:
        try:
            trace_id = attrs.get("trace_id")  # one trace per run: every span joins it
            context = {"trace_id": trace_id} if isinstance(trace_id, str) else None
            metadata = mask({**attrs, **gen_ai_attributes(name, attrs, model)})  # R5: mask last
            client.start_observation(
                trace_context=context,
                name=name,
                as_type="generation" if name == "llm" else "span",
                metadata=metadata,
            ).end()
        except Exception:
            _log.warning("span export failed: %s", name, exc_info=True)

    return export


def configure(settings: Settings, client_factory: Callable[..., Any] | None = None) -> bool:
    public, secret = settings.langfuse_public_key, settings.langfuse_secret_key
    if not (settings.tracing_enabled and public and secret):
        set_exporter(None)
        return False
    if client_factory is None:
        from langfuse import Langfuse  # imported only when tracing is really on

        client_factory = Langfuse
    try:
        client = client_factory(
            public_key=public.get_secret_value(),
            secret_key=secret.get_secret_value(),
            host=settings.langfuse_host,
            mask=mask,
        )
    except Exception:
        _log.warning("Langfuse client could not start; tracing off", exc_info=True)
        set_exporter(None)
        return False
    set_exporter(make_exporter(client, settings.llm_model))
    return True
