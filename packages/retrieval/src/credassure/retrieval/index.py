"""Build the corpus indexes (KR-01/02): corpus.db rows, the FTS5 keyword index and one Chroma
collection per chunking strategy.

Re-runnable: a document whose text, filter metadata, CHUNKER_VERSION and embedding model are
unchanged is skipped. A changed document is replaced, and one no longer in the corpus is
removed. Each document commits on its own, so an interrupted run resumes where it stopped.

BR-15: every chunk passes through the injection scanner. A hit is tagged on the chunk and audited
(INJECTION_FLAGGED). The chunk is still indexed: it is evidence, and stays data, never instructions.
"""

import hashlib
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings

from credassure.retrieval.chunking import (
    CHUNKER_VERSION,
    STRATEGIES,
    Embed,
    by_section,
    fixed,
    semantic,
)
from credassure.retrieval.context import CONTEXT_VERSION, embed_text
from credassure.retrieval.sources import SourceDoc
from credassure.security.injection import scan

Audit = Callable[[str | None, str, dict[str, Any]], None]
_BATCH = 1000  # under Chroma's max batch size


def open_chroma(path: Path | str) -> ClientAPI:
    return chromadb.PersistentClient(
        path=str(path), settings=ChromaSettings(anonymized_telemetry=False, allow_reset=False)
    )


def collection(chroma: ClientAPI, strategy: str) -> Collection:
    return chroma.get_or_create_collection(
        f"chunks_{strategy}", embedding_function=None, metadata={"hnsw:space": "cosine"}
    )


def date_key(value: Any) -> int:
    """YYYYMMDD as an int for Chroma's numeric $lte. An undated document sorts after any as-of."""
    return int(value.strftime("%Y%m%d")) if value else 99991231


@dataclass
class Summary:
    indexed: int = 0
    unchanged: int = 0
    removed: int = 0
    flagged_docs: int = 0
    real: int = 0
    synthetic: int = 0
    chunks: dict[str, int] = field(default_factory=dict)


def _connect(path: Path | str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.execute("PRAGMA busy_timeout=5000")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def _delete(con: sqlite3.Connection, chroma: ClientAPI, doc_id: str) -> None:
    for strategy in STRATEGIES:
        collection(chroma, strategy).delete(where={"doc_id": doc_id})
    con.execute(
        "INSERT INTO chunks_fts (chunks_fts, rowid, text) "
        "SELECT 'delete', rowid, text FROM chunks WHERE doc_id = ?",
        (doc_id,),
    )
    con.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
    con.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))


def _pieces(doc: SourceDoc, embed: Embed) -> Iterable[tuple[str, int, str, str | None]]:
    for strategy, pieces in (
        ("fixed512", fixed(doc.text)),
        ("section", by_section(doc.text)),
        ("semantic", semantic(doc.text, embed)),
    ):
        for ordinal, piece in enumerate(pieces):
            yield strategy, ordinal, piece.text, piece.section_path


Row = tuple[str, str, int, str, str | None, list[str]]


NEVER = 99991231  # superseded_from of a document nothing replaces


def index_version(
    doc: SourceDoc, embed_model: str, superseded_from: int = NEVER, *, headers: bool = False
) -> str:
    """Skip key: text, chunker, embedder AND every filter field, so a metadata-only change (a
    document newly superseded, re-dated or re-scoped) is re-indexed (KR-04)."""
    fields = [
        doc.collection,
        doc.jurisdiction,
        doc.applies_to,
        str(doc.effective_from),
        str(doc.superseded_by),
        str(doc.case_id),
        doc.legal_basis,
        doc.title,
        str(doc.tenant_id),
        str(superseded_from),
    ]
    meta = hashlib.sha256("\0".join(fields).encode()).hexdigest()[:16]
    base = f"{doc.sha256}:{meta}:{CHUNKER_VERSION}:{embed_model}"
    return f"{base}:{CONTEXT_VERSION}" if headers else base  # a toggle re-indexes (scope #61)


def _scan(text: str, path: str | None) -> list[str]:
    # The heading travels with the passage (section_path), so it is scanned with it.
    return scan(f"{path}\n{text}" if path else text)


def _audit_payload(doc: SourceDoc, rows: list[Row]) -> dict[str, Any] | None:
    """One INJECTION_FLAGGED event per document. The whole text is scanned too, so a phrase split
    between two semantic chunks (no overlap) is still on record."""
    flagged = [(r[0], r[5]) for r in rows if r[5]]
    rules = {rule for _, hit in flagged for rule in hit} | set(scan(doc.text)) | set(doc.raw_flags)
    if not rules:
        return None
    return {
        "source": "ingest",
        "doc_id": doc.doc_id,
        "chunk_ids": [chunk_id for chunk_id, _ in flagged],
        "rules": sorted(rules),
        "raw_rules": sorted(doc.raw_flags),
    }


def _index(
    con: sqlite3.Connection,
    chroma: ClientAPI,
    doc: SourceDoc,
    version: str,
    embed: Embed,
    superseded_from: int,
    headers: bool = False,
) -> dict[str, Any] | None:
    rows: list[Row] = [
        (f"{doc.doc_id}#{strategy}#{ordinal}", strategy, ordinal, text, path, _scan(text, path))
        for strategy, ordinal, text, path in _pieces(doc, embed)
    ]
    meta: dict[str, str | int | bool] = {
        "doc_id": doc.doc_id,
        "collection": doc.collection,
        "jurisdiction": doc.jurisdiction,
        "applies_to": doc.applies_to,
        "effective_from": date_key(doc.effective_from),
        # date the replacement takes over (KR-04): 0 = replacement unknown or undated (fail closed)
        "superseded_from": superseded_from,
        "case_id": doc.case_id or "",
        "tenant_id": doc.tenant_id or "",
    }
    _delete(con, chroma, doc.doc_id)
    for strategy in STRATEGIES:
        mine = [r for r in rows if r[1] == strategy]
        for start in range(0, len(mine), _BATCH):
            batch = mine[start : start + _BATCH]
            collection(chroma, strategy).add(
                ids=[r[0] for r in batch],
                embeddings=embed(  # type: ignore[arg-type]
                    [embed_text(doc, strategy, r[3], r[4], on=headers) for r in batch]
                ),
                metadatas=cast(Any, [meta | {"injection_flag": bool(r[5])} for r in batch]),
            )
    con.execute(
        "INSERT INTO documents (doc_id, title, publisher, collection, jurisdiction, applies_to, "
        "effective_from, superseded_by, source_url, sha256, license_note, case_id, legal_basis, "
        "index_version, tenant_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            doc.doc_id,
            doc.title,
            doc.publisher,
            doc.collection,
            doc.jurisdiction,
            doc.applies_to,
            doc.effective_from.isoformat() if doc.effective_from else None,
            doc.superseded_by,
            doc.source_url,
            doc.sha256,
            None,
            doc.case_id,
            doc.legal_basis,
            version,
            doc.tenant_id,
        ),
    )
    for chunk_id, strategy, ordinal, text, path, rules in rows:
        cur = con.execute(
            "INSERT INTO chunks (chunk_id, doc_id, strategy, ordinal, text, section_path, "
            "injection_flag) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (chunk_id, doc.doc_id, strategy, ordinal, text, path, bool(rules)),
        )
        con.execute("INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)", (cur.lastrowid, text))
    return _audit_payload(doc, rows)


def ingest(
    docs: list[SourceDoc],
    *,
    corpus_db: Path | str,
    chroma: ClientAPI,
    embed: Embed,
    embed_model: str,
    audit: Audit,
    progress: Callable[[str], None] | None = None,
    contextual_headers: bool = False,
) -> Summary:
    summary = Summary()
    con = _connect(corpus_db)
    try:
        existing = dict(con.execute("SELECT doc_id, index_version FROM documents").fetchall())
        for doc_id in sorted(existing.keys() - {d.doc_id for d in docs}):
            with con:
                _delete(con, chroma, doc_id)
            summary.removed += 1
        dates = {d.doc_id: d.effective_from for d in docs}
        for n, doc in enumerate(docs, 1):
            replaced = doc.superseded_by and dates.get(doc.superseded_by)
            superseded_from = (
                NEVER if not doc.superseded_by else date_key(replaced) if replaced else 0
            )
            version = index_version(doc, embed_model, superseded_from, headers=contextual_headers)
            if existing.get(doc.doc_id) == version:
                summary.unchanged += 1
            else:
                with con:
                    payload = _index(
                        con, chroma, doc, version, embed, superseded_from, contextual_headers
                    )
                if payload:  # audited only once the corpus rows are committed
                    audit(doc.case_id, "INJECTION_FLAGGED", payload)
                summary.indexed += 1
            if progress and n % 25 == 0:
                progress(f"{n}/{len(docs)} documents ({summary.indexed} indexed)")
        summary.real = sum(1 for d in docs if d.real)
        summary.synthetic = len(docs) - summary.real
        summary.flagged_docs = con.execute(
            "SELECT count(DISTINCT doc_id) FROM chunks WHERE injection_flag"
        ).fetchone()[0]
        summary.chunks = dict(
            con.execute("SELECT strategy, count(*) FROM chunks GROUP BY strategy").fetchall()
        )
    finally:
        con.close()
    return summary
