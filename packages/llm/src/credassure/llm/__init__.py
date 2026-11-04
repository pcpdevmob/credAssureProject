"""Model access. This package is the only one that may import the OpenAI SDK (ADR 0005)."""

import openai


def sdk_name() -> str:
    """Return the SDK package name. Exists so the import is real and the boundary can be checked."""
    return openai.__name__
