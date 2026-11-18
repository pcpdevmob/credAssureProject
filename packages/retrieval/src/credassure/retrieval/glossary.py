"""Deterministic glossary query rewrite (plan v3.4 §7.1, scope #62). No model call.

`config/glossary.yaml` maps each domain acronym to its expansions. The file was written from the
domain (RBI, CGTMSE, GST and MSME terminology in the corpus manifest), never from test or dev
queries. A query that contains an acronym gains its expansion, and a query that contains an
expansion gains the acronym, so keyword and dense search both see both forms. The reranker still
scores against the user's own words.
"""

import re
from functools import cache
from pathlib import Path

import yaml

GLOSSARY = Path(__file__).resolve().parents[5] / "config" / "glossary.yaml"


@cache
def terms(path: Path = GLOSSARY) -> tuple[tuple[str, tuple[str, ...]], ...]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return tuple((str(k), tuple(str(e) for e in v)) for k, v in sorted(data["terms"].items()))


def _has(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text, re.IGNORECASE) is not None


def rewrite(query: str, path: Path = GLOSSARY) -> str:
    """`query` plus the missing forms of every glossary term it mentions, in glossary order."""
    extra: list[str] = []
    for acronym, expansions in terms(path):
        forms = (acronym, *expansions)
        if any(_has(query, f) for f in forms):
            extra += [f for f in forms if not _has(query, f) and f not in extra]
    return f"{query} ({'; '.join(extra)})" if extra else query
