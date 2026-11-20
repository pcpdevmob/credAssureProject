"""Evaluation reproducibility record (scope #13): what produced a set of results.

Every run writes record.json with the model, endpoint, context length (EVAL_NUM_CTX) and run kind
(graded / local_provisional / smoke_test), prompt versions (SHA-256), the engine version
(last git commit touching packages/engines), the corpus hash (manifest + lock), the data hash (v1 SHA256SUMS) and every frozen version's SHA256SUMS,
the test-set hash, the seed, the item count and the UTC time.
"""

import hashlib
import os
import subprocess  # nosec B404 - fixed argv only
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from credassure.core.prompts import versions as registry_versions

from .gold.data import REPO


def _sha(*paths: str) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update((REPO / p).read_bytes())
    return h.hexdigest()


def data_hashes() -> dict[str, str]:
    """SHA-256 of every frozen data version's manifest (v1, v2 lender scripts since ADR 0037, ...)."""
    return {
        str(p.relative_to(REPO)): _sha(str(p.relative_to(REPO)))
        for p in sorted((REPO / "data" / "frozen").glob("v*/SHA256SUMS"))
    }


def engine_version() -> str:
    result = subprocess.run(  # nosec B603 B607 - fixed argv, git from PATH
        ["git", "log", "-1", "--format=%H", "--", "packages/engines"],  # noqa: S607
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal", "ollama"}


def run_kind(endpoint: str, context_length: int | None) -> str:
    """Only a run on the course endpoint is graded (BRD §12). A local run is provisional when the context
    length was set explicitly (EVAL_NUM_CTX, matching OLLAMA_CONTEXT_LENGTH); otherwise a smoke test."""
    host = urlparse(endpoint).hostname or ""
    if host not in LOCAL_HOSTS:
        return "graded"
    return "local_provisional" if context_length else "smoke_test"


def run_record(
    model: str, endpoint: str, prompts: dict[str, str], items: int, strategy: str
) -> dict[str, Any]:
    num_ctx = os.environ.get("EVAL_NUM_CTX")
    context_length = int(num_ctx) if num_ctx else None
    return {
        "strategy": strategy,
        "model": model,
        "endpoint": endpoint,
        "context_length": context_length,
        "run_kind": run_kind(endpoint, context_length),
        "prompt_versions": {
            name: hashlib.sha256(text.encode()).hexdigest()[:16]
            for name, text in sorted(prompts.items())
        },
        "system_prompt_versions": registry_versions(),  # scope #36: the registry's prompts
        "engine_version": engine_version(),
        "corpus_hash": _sha("data/corpus/manifest.yaml", "data/corpus/manifest.lock.json"),
        "data_hash": _sha("data/frozen/v1/SHA256SUMS"),
        "data_hashes": data_hashes(),
        "testset_hash": _sha("evaluation/testset/v1/items.jsonl"),
        "seed": int(os.environ.get("CREDASSURE_SEED", "20261026")),
        "items": items,
        "utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
