"""Structured output lives in ``credassure.core.structured`` (it needs only the LLM port, so
agents can use it without importing this adapter package, ADR 0006). Re-exported here."""

from credassure.core.structured import MAX_REPAIRS, StructuredOutputError, complete_model

__all__ = ["MAX_REPAIRS", "StructuredOutputError", "complete_model"]
