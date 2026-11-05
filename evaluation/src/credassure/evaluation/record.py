"""Evaluation reproducibility record (scope #13): what produced a set of results.

Every run writes record.json with the model and endpoint, prompt versions (SHA-256), the engine version
(last git commit touching packages/engines), the corpus hash (manifest + lock), the data hash (SHA256SUMS),
the test-set hash, the seed, the item count and the UTC time.
"""

import hashlib
import os
import subprocess  # nosec B404 - fixed argv only
from datetime import UTC, datetime
from typing import Any

from .gold.data import REPO


def _sha(*paths: str) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update((REPO / p).read_bytes())
    return h.hexdigest()


def engine_version() -> str:
    result = subprocess.run(  # nosec B603 B607 - fixed argv, git from PATH
        ["git", "log", "-1", "--format=%H", "--", "packages/engines"],  # noqa: S607
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def run_record(
    model: str, endpoint: str, prompts: dict[str, str], items: int, strategy: str
) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "model": model,
        "endpoint": endpoint,
        "prompt_versions": {
            name: hashlib.sha256(text.encode()).hexdigest()[:16]
            for name, text in sorted(prompts.items())
        },
        "engine_version": engine_version(),
        "corpus_hash": _sha("data/corpus/manifest.yaml", "data/corpus/manifest.lock.json"),
        "data_hash": _sha("data/frozen/v1/SHA256SUMS"),
        "testset_hash": _sha("evaluation/testset/v1/items.jsonl"),
        "seed": int(os.environ.get("CREDASSURE_SEED", "20261026")),
        "items": items,
        "utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }
