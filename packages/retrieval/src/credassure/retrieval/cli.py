"""`make ingest`: index data/corpus (real, ADR 0019) and data/frozen/v1 (synthetic KFS + policies).

Reads its configuration from the environment like `make llm-probe` (packages never import the
gateway's Settings): EMBED_BASE_URL, EMBED_MODEL, EMBED_API_KEY (else LLM_API_KEY for the same
host), EMBED_CA_CERT (CA file for a self-signed endpoint), EMBED_BATCH (default 16, the course
limit), EMBED_LOCAL_MODEL / EMBED_LOCAL_REVISION (EMBED_BASE_URL=local), CORPUS_DB, CASE_DB
(audit), CHROMA_PATH, EMBED_CACHE_PATH, EMBED_RATE_PER_MINUTE, TENANT_ID.
"""

import os
import ssl
import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

import httpx2

from credassure.ledger import migrate
from credassure.ledger.session import case_engine
from credassure.ledger.store import SqlLedger
from credassure.llm.cache import ResponseCache
from credassure.llm.embed import OpenAIEmbedder
from credassure.llm.resilience import RateLimiter
from credassure.retrieval.chunking import Embed
from credassure.retrieval.index import ingest, open_chroma
from credassure.retrieval.sources import load_corpus

TARGET_REAL = 500  # BRD G2
LOCAL_EMBED = ("http://localhost:11434/v1", "nomic-embed-text")  # ADR 0017 default, as .env.example
# EMBED_BASE_URL=local: the course model run in-process, same 384-dim space as the course endpoint.
# The HF id differs from the course name "bge-small-en-v1.5", so cache and index keys stay apart.
IN_PROCESS = "BAAI/bge-small-en-v1.5"


def embed_target(env: Mapping[str, str]) -> tuple[str, str]:
    if env.get("EMBED_BASE_URL") == "local":
        return "local", env.get("EMBED_LOCAL_MODEL") or IN_PROCESS
    return env.get("EMBED_BASE_URL") or LOCAL_EMBED[0], env.get("EMBED_MODEL") or LOCAL_EMBED[1]


def endpoint(url: str) -> str:
    """Scheme and host only: never print credentials or query strings from a URL."""
    if url == "local":
        return "in-process sentence-transformers"
    p = urlparse(url)
    return f"{p.scheme}://{p.hostname}" + (f":{p.port}" if p.port else "")


def api_key(env: Mapping[str, str], url: str) -> str | None:
    """EMBED_API_KEY, else LLM_API_KEY only when embeddings go to the same host as the model."""
    same = urlparse(url).hostname == urlparse(env.get("LLM_BASE_URL", "")).hostname
    return env.get("EMBED_API_KEY") or (env.get("LLM_API_KEY") if same else None)


def local_embedder(model: str, revision: str | None) -> Embed:
    from sentence_transformers import SentenceTransformer  # lazy, like make_reranker (ADR 0013)

    # ponytail: no embed cache here; local encoding is cheap. Set EMBED_LOCAL_REVISION to pin.
    encoder = SentenceTransformer(model, revision=revision)  # remote code stays off (default)

    def embed(texts: list[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in encoder.encode(texts, normalize_embeddings=True)]

    return embed


def embedder(env: Mapping[str, str]) -> Embed:
    url, model = embed_target(env)
    if url == "local":
        return local_embedder(model, env.get("EMBED_LOCAL_REVISION") or None)
    ca = env.get("EMBED_CA_CERT")
    return OpenAIEmbedder(
        url,
        api_key(env, url),
        model,
        batch=int(env.get("EMBED_BATCH", "16")),  # course endpoint: at most 16 texts per request
        http_client=httpx2.Client(verify=ssl.create_default_context(cafile=ca)) if ca else None,
        limiter=RateLimiter(float(env.get("EMBED_RATE_PER_MINUTE", "600"))),
        cache=ResponseCache(env.get("EMBED_CACHE_PATH", "var/embed_cache.db")),
    )


def paths(env: Mapping[str, str]) -> tuple[Path, Path, Path]:
    return (
        Path(env.get("CORPUS_DB", "var/corpus.db")),
        Path(env.get("CASE_DB", "var/case.db")),
        Path(env.get("CHROMA_PATH", "var/chroma")),
    )


def main(env: Mapping[str, str] = os.environ) -> int:
    corpus_db, case_db, chroma_path = paths(env)
    migrate.upgrade("corpus", corpus_db)
    migrate.upgrade("case", case_db)
    ledger = SqlLedger(case_engine(case_db), env.get("TENANT_ID", "default"), actor="ingest")
    url, model = embed_target(env)
    print(f"ingest: embeddings from {model} at {endpoint(url)}", file=sys.stderr)
    docs = load_corpus(Path.cwd())
    summary = ingest(
        docs,
        corpus_db=corpus_db,
        chroma=open_chroma(chroma_path),
        embed=embedder(env),
        embed_model=model,
        audit=ledger.audit,
        contextual_headers=env.get("RETRIEVAL_CONTEXT_HEADERS", "false").lower() == "true",
        progress=lambda line: print(line, file=sys.stderr, flush=True),
    )
    print(
        f"ingest: {summary.real} real + {summary.synthetic} synthetic documents; "
        f"{summary.indexed} indexed, {summary.unchanged} unchanged, {summary.removed} removed; "
        f"chunks {summary.chunks}; {summary.flagged_docs} documents with injection-flagged chunks"
    )
    if summary.real < TARGET_REAL:
        print(
            f"ingest: WARNING {summary.real} real documents < {TARGET_REAL} (G2)", file=sys.stderr
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
