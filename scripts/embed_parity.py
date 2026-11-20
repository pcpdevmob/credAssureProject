"""Can the course endpoint's embeddings reuse the local vector index? (course comparison, ADR 0036)

    make embed-parity MODELS=course            # 40 chunks, about a minute on the course endpoint

The local index (`var/chroma-local-bge`) was built in-process with BAAI/bge-small-en-v1.5; the
course endpoint serves the same model. Re-embedding the corpus there means about 115,000 chunks
at the endpoint's rate limit (about two hours). This embeds a seeded sample of chunks both ways and
reports the cosine similarity of each pair. If every pair is at least 0.999 the vectors are the
same for retrieval, and the local index can be copied to `var/chroma-course-bge` instead of
re-ingesting.
Queries are still embedded by the course endpoint at run time.

Reads var/corpus.db read-only. Prints scores only, never chunk text, keys or URLs with credentials.
"""

import argparse
import math
import os
import random
import sqlite3
import sys
from pathlib import Path

from credassure.retrieval.cli import IN_PROCESS, embed_target, embedder, endpoint, local_embedder

THRESHOLD = 0.999


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def sample(corpus: Path, n: int, seed: int) -> list[str]:
    con = sqlite3.connect(f"file:{corpus}?mode=ro", uri=True)
    try:
        ids = [r[0] for r in con.execute("SELECT chunk_id FROM chunks ORDER BY chunk_id")]
        picked = random.Random(seed).sample(ids, min(n, len(ids)))  # noqa: S311  # nosec B311 (sampling, not security)
        marks = ",".join("?" * len(picked))
        rows = con.execute(f"SELECT text FROM chunks WHERE chunk_id IN ({marks})", picked)  # noqa: S608  # nosec B608
        return [r[0] for r in rows]
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("-n", type=int, default=40, help="chunks to compare")
    ap.add_argument("--seed", type=int, default=20261120)
    args = ap.parse_args()
    env = dict(os.environ)
    url, model = embed_target(env)
    if url == "local":
        sys.exit("run with MODELS=course: this compares the course endpoint with the local model")
    texts = sample(Path(env.get("CORPUS_DB", "var/corpus.db")), args.n, args.seed)
    print(
        f"course: {model} at {endpoint(url)}; local: {IN_PROCESS} in-process; {len(texts)} chunks"
    )
    remote = embedder(env)(texts)
    local = local_embedder(IN_PROCESS, env.get("EMBED_LOCAL_REVISION") or None)(texts)
    if len(remote[0]) != len(local[0]):
        print(f"dimension differs: course {len(remote[0])}, local {len(local[0])} -> re-ingest")
        return 1
    scores = sorted(cosine(a, b) for a, b in zip(remote, local, strict=True))
    print(
        f"cosine min {scores[0]:.5f}  median {scores[len(scores) // 2]:.5f}  max {scores[-1]:.5f}"
    )
    if scores[0] >= THRESHOLD:
        print(
            f"SAME (every pair >= {THRESHOLD}): copy the local index instead of re-ingesting:\n"
            "  cp -R var/chroma-local-bge var/chroma-course-bge"
        )
        return 0
    print(f"DIFFERENT (some pair < {THRESHOLD}): re-ingest with `make ingest MODELS=course` (~2 h)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
