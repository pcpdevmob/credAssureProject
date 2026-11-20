"""Can the course endpoint's embeddings reuse the local vector index? (course comparison, ADR 0036)

    make embed-parity MODELS=course            # 40 chunks, about a minute on the course endpoint

The local index (`var/chroma-local-bge`) was built in-process with BAAI/bge-small-en-v1.5; the
course endpoint serves the same model. Re-embedding the corpus there means about 115,000 chunks
at the endpoint's rate limit (about two hours). This embeds a seeded sample of chunks both ways and
reports the cosine similarity of each pair. If every pair is at least 0.999 the vectors are the
same for retrieval, and the local index can be copied to `var/chroma-course-bge` instead of
re-ingesting. Only chunks of at most 510 tokens are compared: the course endpoint refuses longer
inputs (the local model truncates them), so `make ingest MODELS=course` would fail on long chunks
anyway and copying the local index is the only route for them.
Queries are still embedded by the course endpoint at run time.

Reads var/corpus.db read-only. Prints scores only, never chunk text, keys or URLs with credentials.
"""

import argparse
import math
import os
import random
import sqlite3
import sys
from collections.abc import Callable
from pathlib import Path

from credassure.retrieval.cli import IN_PROCESS, embed_target, embedder, endpoint, local_embedder

THRESHOLD = 0.999


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


MAX_TOKENS = (
    510  # the course endpoint (TEI) refuses inputs over 512 tokens; the local model truncates
)


def sample(corpus: Path, n: int, seed: int, fits: Callable[[str], bool]) -> list[str]:
    """n chunks in seeded random order, skipping any the endpoint would refuse as too long."""
    con = sqlite3.connect(f"file:{corpus}?mode=ro", uri=True)
    try:
        ids = [r[0] for r in con.execute("SELECT chunk_id FROM chunks ORDER BY chunk_id")]
        random.Random(seed).shuffle(ids)  # noqa: S311  # nosec B311 (sampling, not security)
        out: list[str] = []
        for cid in ids:
            (text,) = con.execute("SELECT text FROM chunks WHERE chunk_id = ?", (cid,)).fetchone()
            if fits(text):
                out.append(text)
                if len(out) == n:
                    break
        return out
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
    from sentence_transformers import SentenceTransformer  # lazy, like the ingest

    tokenizer = SentenceTransformer(IN_PROCESS).tokenizer
    texts = sample(
        Path(env.get("CORPUS_DB", "var/corpus.db")),
        args.n,
        args.seed,
        lambda t: len(tokenizer(t)["input_ids"]) <= MAX_TOKENS,
    )
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
