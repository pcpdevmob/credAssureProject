"""Protected-attribute field denylist (plan v3.4 P8.3, scope #67, ADR 0029 rail R1).

Case files carry amounts, dates and synthetic names only. A JSON key or CSV header that names a
protected attribute (gender, religion, caste, age, ...) is refused at upload, so such a field can
never reach a gate, a ranking or a prompt, even though Pydantic would silently drop it. The word
lists live in `config/guardrails.yaml` (`protected_attributes`). Values are never inspected: names
like "Fatima Traders" are ordinary data and the fairness invariance test proves they change nothing.
"""

import csv
import io
import json
import re
from collections.abc import Iterable, Iterator
from typing import Any

from credassure.guardrails.policy import Policy, load

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SPLIT = re.compile(r"[^a-z0-9]+")
_MAX_KEYS = 10_000


def _normalise(name: str) -> tuple[str, list[str]]:
    words = [w for w in _SPLIT.split(_CAMEL.sub("_", name).lower()) if w]
    return "_".join(words), words


def matches(name: str, policy: Policy | None = None) -> bool:
    p = policy or load()
    joined, words = _normalise(name)
    return joined in p.protected_exact or any(w in p.protected_tokens for w in words)


def _json_keys(node: Any, depth: int = 0) -> Iterator[str]:
    if depth > 64:
        return
    if isinstance(node, dict):
        for k, v in node.items():
            yield str(k)
            yield from _json_keys(v, depth + 1)
    elif isinstance(node, list):
        for v in node:
            yield from _json_keys(v, depth + 1)


def field_names(text: str, *, is_json: bool) -> list[str]:
    """Every key (JSON, any depth) or the header row (CSV). Unparseable text gives [] and is left
    to the schema validator, which rejects it with its own message."""
    try:
        if is_json:
            names: Iterable[str] = _json_keys(json.loads(text))
        else:
            names = next(csv.reader(io.StringIO(text)), [])
        out: list[str] = []
        for n in names:
            out.append(n)
            if len(out) >= _MAX_KEYS:
                break
        return out
    except (ValueError, RecursionError, csv.Error):
        return []


def find(text: str, *, is_json: bool, policy: Policy | None = None) -> list[str]:
    """Protected field names in the file, de-duplicated in first-seen order."""
    p = policy or load()
    seen: dict[str, None] = {}
    for n in field_names(text, is_json=is_json):
        if n not in seen and matches(n, p):
            seen[n] = None
    return list(seen)
