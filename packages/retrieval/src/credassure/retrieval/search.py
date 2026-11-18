"""search_knowledge (KR-02..04): BM25 over FTS5 and dense over Chroma, fused by reciprocal rank
(k=60), optionally reranked top-30 → top-k.

The ADR 0019 filters run inside both retrievers, before ranking, and again in SQL on the final rows,
so a passage that is not in force for this case can never be returned:
  effective_from ≤ as_of · not superseded (a replacement in force on as_of; an unknown or undated
  replacement counts as in force) · jurisdiction ∈ {IN, home state} · applies_to ∈ {all, lender
  type} · case-scoped documents (KFS) only for their own (tenant, case) (BR-14, SUP-08).
A case may also read the corpus KFS it uploaded itself (``Filters.own_kfs``: doc_id + content sha of
its kfs case files), whatever their tagged case or lender type (9e, user decision 2026-11-16): the
frozen KFS are tagged to CA-2026-0001..0015, while API cases get later ids.
"""

import re
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from chromadb.api import ClientAPI

from credassure.retrieval import glossary
from credassure.retrieval.chunking import Embed
from credassure.retrieval.index import collection, date_key
from credassure.security.pii import redact

Mode = Literal["keyword", "dense", "hybrid"]
Reranker = Callable[[str, list[str]], list[float]]
DEPTH = 30
# BAAI/bge-reranker-base pinned to a reviewed commit (2024-06-24); change only with a re-run eval.
RERANKER_REVISION = "2cfc18c9415c912f9d8155881c133215df768a70"


@dataclass(frozen=True)
class Filters:
    as_of: date
    home_state: str = "IN-MH"
    lender_type: str = "commercial_bank"  # ADR 0019: from the offer; case-free questions → this
    collections: tuple[str, ...] | None = None
    own_kfs: frozenset[str] = frozenset()  # "doc_id@sha256" of the case's uploaded KFS


def _own(f: Filters) -> tuple[str, dict[str, Any]]:
    """SQL for "this KFS was uploaded to the case" (exact text: doc_id and sha both match), and
    the document is shared (tenant NULL) or this tenant's: another tenant's KFS never matches,
    even with the same id and bytes (SUP-08, BR-14). Binds ``:tenant_id`` from the caller."""
    if not f.own_kfs:
        return "0", {}
    names = {f"own{i}": v for i, v in enumerate(sorted(f.own_kfs))}
    marks = ", ".join(":" + n for n in names)
    return (
        f"(d.collection = 'kfs' AND d.doc_id || '@' || d.sha256 IN ({marks})"
        " AND (d.tenant_id IS NULL OR d.tenant_id = :tenant_id))"
    ), names


@dataclass(frozen=True)
class Passage:
    chunk_id: str
    doc_id: str
    title: str
    collection: str
    section_path: str | None
    effective_from: date | None
    text: str
    injection_flag: bool


@dataclass(frozen=True)
class PassageDetail:
    """One cited chunk with what a reader needs to check it (UI-06)."""

    chunk_id: str
    doc_id: str
    title: str
    section_path: str | None
    effective_from: date | None
    legal_basis: str | None
    source_url: str | None
    text: str


def rrf(rankings: Sequence[Sequence[str]], k: int = 60) -> list[str]:
    score: dict[str, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, 1):
            score[item] = score.get(item, 0.0) + 1.0 / (k + rank)
    return sorted(score, key=lambda item: -score[item])


def make_reranker(setting: str, model: str, revision: str = RERANKER_REVISION) -> Reranker | None:
    """ADR 0013: none by default; the cross-encoder only behind RERANKER=local_cross_encoder."""
    if setting == "none":
        return None
    if setting != "local_cross_encoder":
        raise ValueError(
            f"RERANKER={setting} is not built; use none or local_cross_encoder (ADR 0013)"
        )
    from sentence_transformers import CrossEncoder

    encoder = CrossEncoder(model, revision=revision)  # remote code stays off (default)

    def rerank(query: str, texts: list[str]) -> list[float]:
        return [float(s) for s in encoder.predict([(query, t) for t in texts])]

    return rerank


def _fts_query(query: str) -> str:
    """Every word as a quoted FTS5 term, OR-ed: user text can never be FTS5 syntax."""
    return " OR ".join(f'"{w}"' for w in re.findall(r"\w+", query.lower()) if len(w) > 1)


class Searcher:
    def __init__(
        self,
        corpus_db: Path | str,
        chroma: ClientAPI | None,
        embed: Embed | None,
        *,
        reranker: Reranker | None = None,
        strategy: str = "section",
        as_of: date | None = None,
        tenant_id: str | None = None,
        ablation: str | None = None,
        query_rewrite: bool = False,
        min_score: float | None = None,
    ) -> None:
        self._db, self._chroma, self._embed = Path(corpus_db), chroma, embed
        self.reranker, self.strategy, self.as_of = reranker, strategy, as_of
        self.tenant_id = tenant_id
        self.ablation = ablation  # A3: semantic top five only (BRD §12)
        self.query_rewrite = query_rewrite  # scope #62: glossary expansion, no model call
        self.min_score = min_score  # scope #63: answerability gate on the top reranker score

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self._db}?mode=ro", uri=True)

    @staticmethod
    def _where(
        case_id: str | None, tenant_id: str | None, f: Filters
    ) -> tuple[str, dict[str, Any]]:
        params: dict[str, Any] = {
            "as_of": f.as_of.isoformat(),
            "home": f.home_state,
            "lender": f.lender_type,
            "case_id": case_id,
            "tenant_id": tenant_id,
        }
        own, own_params = _own(f)
        params |= own_params
        sql = (
            "d.effective_from IS NOT NULL AND d.effective_from <= :as_of"  # noqa: S608  # nosec B608
            " AND (d.superseded_by IS NULL OR EXISTS (SELECT 1 FROM documents r"
            " WHERE r.doc_id = d.superseded_by AND r.effective_from > :as_of))"
            " AND d.jurisdiction IN ('IN', :home)"
            f" AND (d.applies_to IN ('all', :lender) OR {own})"
            " AND (d.case_id IS NULL OR (d.case_id = :case_id AND d.tenant_id = :tenant_id)"
            f" OR {own})"
        )
        if f.collections is not None:
            names = {f"c{i}": c for i, c in enumerate(f.collections)}
            sql += f" AND d.collection IN ({', '.join(':' + n for n in names) or 'NULL'})"
            params |= names
        return sql, params

    def keyword(
        self,
        query: str,
        case_id: str | None,
        tenant_id: str | None,
        f: Filters,
        strategy: str,
        n: int,
    ) -> list[str]:
        match = _fts_query(query)
        if not match:
            return []
        where, params = self._where(case_id, tenant_id, f)
        sql = (
            "SELECT c.chunk_id FROM chunks_fts JOIN chunks c ON c.rowid = chunks_fts.rowid"  # noqa: S608  # nosec B608
            " JOIN documents d ON d.doc_id = c.doc_id"
            f" WHERE chunks_fts MATCH :match AND c.strategy = :strategy AND {where}"
            " ORDER BY bm25(chunks_fts) LIMIT :n"
        )  # `where` is fixed text and every value is a bound parameter
        with self._connect() as con:
            rows = con.execute(sql, params | {"match": match, "strategy": strategy, "n": n})
            return [r[0] for r in rows]

    def dense(
        self,
        query: str,
        case_id: str | None,
        tenant_id: str | None,
        f: Filters,
        strategy: str,
        n: int,
    ) -> list[str]:
        if not query.strip() or self._chroma is None or self._embed is None:
            return []  # keyword-only searcher (no vector store configured)
        own_docs = sorted({o.split("@", 1)[0] for o in f.own_kfs})
        tenants = ["", tenant_id] if tenant_id else [""]  # "" = shared (tenant NULL)
        mine: list[dict[str, Any]] = (
            [{"$and": [{"doc_id": {"$in": own_docs}}, {"tenant_id": {"$in": tenants}}]}]
            if own_docs
            else []
        )
        scope: list[dict[str, Any]] = [{"case_id": ""}, *mine]
        if case_id and tenant_id:
            scope.append({"$and": [{"case_id": case_id}, {"tenant_id": tenant_id}]})
        lender: dict[str, Any] = {"applies_to": {"$in": ["all", f.lender_type]}}
        clauses: list[dict[str, Any]] = [  # the SQL re-check below also matches the sha
            {"effective_from": {"$lte": date_key(f.as_of)}},
            {"superseded_from": {"$gt": date_key(f.as_of)}},
            {"jurisdiction": {"$in": ["IN", f.home_state]}},
            {"$or": [lender, *mine]} if mine else lender,
            {"$or": scope} if len(scope) > 1 else scope[0],
        ]
        if f.collections is not None:
            clauses.append({"collection": {"$in": list(f.collections) or [""]}})
        found = collection(self._chroma, strategy).query(
            # redacted: the query leaves the process for the embedding endpoint
            query_embeddings=self._embed([redact(query)]),  # type: ignore[arg-type]
            n_results=n,
            where={"$and": clauses},
            include=[],
        )
        return list(found["ids"][0]) if found["ids"] else []

    def _passages(
        self, ids: list[str], case_id: str | None, tenant_id: str | None, f: Filters
    ) -> list[Passage]:
        if not ids:
            return []
        where, params = self._where(case_id, tenant_id, f)
        marks = ", ".join(f":id{i}" for i in range(len(ids)))
        sql = (
            "SELECT c.chunk_id, c.doc_id, d.title, d.collection, c.section_path,"  # noqa: S608  # nosec B608
            " d.effective_from,"
            " c.text, c.injection_flag FROM chunks c JOIN documents d ON d.doc_id = c.doc_id"
            f" WHERE c.chunk_id IN ({marks}) AND {where}"
        )  # placeholders and fixed text only; every value is bound
        with self._connect() as con:
            rows = con.execute(sql, params | {f"id{i}": v for i, v in enumerate(ids)}).fetchall()
        found = {
            r[0]: Passage(
                r[0],
                r[1],
                r[2],
                r[3],
                r[4],
                date.fromisoformat(r[5]) if r[5] else None,
                r[6],
                bool(r[7]),
            )
            for r in rows
        }
        return [found[i] for i in ids if i in found]

    def passage(
        self, chunk_id: str, case_id: str | None, tenant_id: str | None, f: Filters
    ) -> PassageDetail | None:
        """The chunk if the ADR 0019 filter that governs search admits it for this case, else
        None. Missing, superseded, other state or lender type, another case's or tenant's KFS all
        read the same, so a caller cannot probe which documents exist (SUP-08)."""
        where, params = self._where(case_id, tenant_id, f)
        sql = (
            "SELECT c.chunk_id, c.doc_id, d.title, c.section_path, d.effective_from,"  # noqa: S608  # nosec B608
            " d.legal_basis, d.source_url, c.text FROM chunks c"
            f" JOIN documents d ON d.doc_id = c.doc_id WHERE c.chunk_id = :chunk AND {where}"
        )  # fixed text; every value is a bound parameter
        with self._connect() as con:
            r = con.execute(sql, params | {"chunk": chunk_id}).fetchone()
        if r is None:
            return None
        return PassageDetail(
            r[0], r[1], r[2], r[3], date.fromisoformat(r[4]) if r[4] else None, r[5], r[6], r[7]
        )

    def search_knowledge(
        self,
        query: str,
        *,
        case_id: str | None = None,
        tenant_id: str | None = None,
        filters: Filters,
        strategy: str | None = None,
        mode: Mode = "hybrid",
        k: int = 5,
        rerank: bool = True,
    ) -> list[Passage]:
        """Top passages. With an answerability threshold set and the reranker on, a result whose
        best score is below the threshold is empty, so the copilot abstains (CP-02, scope #63)."""
        scored = self.scored(
            query,
            case_id=case_id,
            tenant_id=tenant_id,
            filters=filters,
            strategy=strategy,
            mode=mode,
            k=k,
            rerank=rerank,
        )
        top = scored[0][1] if scored else None
        if self.min_score is not None and top is not None and top < self.min_score:
            return []
        return [p for p, _ in scored]

    def scored(
        self,
        query: str,
        *,
        case_id: str | None = None,
        tenant_id: str | None = None,
        filters: Filters,
        strategy: str | None = None,
        mode: Mode = "hybrid",
        k: int = 5,
        rerank: bool = True,
    ) -> list[tuple[Passage, float | None]]:
        """(passage, reranker score or None) in rank order. Search reads the glossary-expanded
        query when rewrite is on; the reranker always scores the user's own words."""
        strategy = strategy or self.strategy
        expanded = glossary.rewrite(query) if self.query_rewrite else query
        rankings = []
        if mode in ("keyword", "hybrid"):
            rankings.append(self.keyword(expanded, case_id, tenant_id, filters, strategy, DEPTH))
        if mode in ("dense", "hybrid"):
            rankings.append(self.dense(expanded, case_id, tenant_id, filters, strategy, DEPTH))
        passages = self._passages(rrf(rankings)[:DEPTH], case_id, tenant_id, filters)
        if rerank and self.reranker and passages:
            scores = self.reranker(query, [p.text for p in passages])
            order = sorted(range(len(passages)), key=lambda i: -scores[i])
            ranked: list[tuple[Passage, float | None]] = [(passages[i], scores[i]) for i in order]
            return ranked[:k]
        return [(p, None) for p in passages[:k]]

    def resolve(
        self, ids: Sequence[str], case_id: str | None, filters: Filters
    ) -> dict[str, tuple[str, str]]:
        return resolve(self._db, ids, case_id=case_id, tenant_id=self.tenant_id, filters=filters)

    def search(self, query: str, case_id: str | None) -> list[str]:
        """RetrievalPort: chunk ids of the top passages, filtered as of the configured date.
        Ablation A3: dense search only, top five, no keyword fusion and no reranking."""
        if self.as_of is None:
            raise ValueError("Searcher needs as_of to serve RetrievalPort")
        a3 = self.ablation == "A3"
        return [
            p.chunk_id
            for p in self.search_knowledge(
                query,
                case_id=case_id,
                tenant_id=self.tenant_id,
                filters=Filters(self.as_of),
                mode="dense" if a3 else "hybrid",
                rerank=not a3,
            )
        ]


# Another case's KFS reads as missing: a citation cannot probe whether it exists (SUP-08).
_VISIBLE = " AND (d.case_id IS NULL OR (d.case_id = :case AND d.tenant_id = :tenant) OR {own})"
_DOC = "SELECT d.doc_id FROM documents d WHERE d.doc_id = :c" + _VISIBLE  # noqa: S608  # nosec B608
_CHUNK_DOC = (
    "SELECT d.doc_id FROM documents d JOIN chunks c ON c.doc_id = d.doc_id WHERE c.chunk_id = :c"  # noqa: S608  # nosec B608
    + _VISIBLE
)


def resolve(
    corpus_db: Path | str,
    ids: Sequence[str],
    *,
    case_id: str | None,
    tenant_id: str | None,
    filters: Filters,
    known: Mapping[str, str | None] | None = None,
) -> dict[str, tuple[str, str]]:
    """VER-02: each cited document or chunk id -> (status, passage text) for the Critic.

    ``ok`` only when the same ADR 0019 filter as search admits it (one definition of "in force");
    otherwise the row is classified without returning its text: ``superseded`` (not in force on
    as_of), ``filtered`` (other state, other lender type, other case or collection) or ``missing``.
    ``known`` maps manifest doc ids that were never indexed to their ``superseded_by``, so citing a
    superseded but unindexed document still reads as superseded.
    """
    where, params = Searcher._where(case_id, tenant_id, filters)
    own, own_params = _own(filters)
    in_force = (
        "d.effective_from IS NOT NULL AND d.effective_from <= :as_of"
        " AND (d.superseded_by IS NULL OR EXISTS (SELECT 1 FROM documents r"
        " WHERE r.doc_id = d.superseded_by AND r.effective_from > :as_of))"
    )
    out: dict[str, tuple[str, str]] = {}
    con = sqlite3.connect(f"file:{corpus_db}?mode=ro", uri=True)
    try:
        for cid in ids:
            chunk = "#" in cid
            # The chunk's own document (not parsed from the id); another case's KFS reads as
            # missing, so a citation cannot probe whether another case's document exists.
            exists = con.execute(
                (_CHUNK_DOC if chunk else _DOC).format(own=own),
                {"c": cid, "case": case_id, "tenant": tenant_id, "tenant_id": tenant_id}
                | own_params,
            ).fetchone()
            doc_id = str(exists[0]) if exists else cid.split("#", 1)[0]
            if exists is None:
                if not chunk and known is not None and doc_id in known:
                    out[cid] = ("superseded" if known[doc_id] else "missing", "")
                else:
                    out[cid] = ("missing", "")
                continue
            # fixed SQL text only (the shared ADR 0019 clause); every value is bound
            admitted = f"SELECT 1 FROM documents d WHERE d.doc_id = :doc AND {where}"  # noqa: S608  # nosec B608
            current = f"SELECT 1 FROM documents d WHERE d.doc_id = :doc AND {in_force}"  # noqa: S608  # nosec B608
            if con.execute(admitted, params | {"doc": doc_id}).fetchone() is None:
                live = con.execute(current, params | {"doc": doc_id}).fetchone()
                out[cid] = ("filtered" if live else "superseded", "")
                continue
            if chunk:
                row = con.execute("SELECT text FROM chunks WHERE chunk_id = :c", {"c": cid})
                out[cid] = ("ok", str(row.fetchone()[0]))
                continue
            strategy = con.execute(
                "SELECT strategy FROM chunks WHERE doc_id = :d ORDER BY strategy = 'section' DESC"
                " LIMIT 1",
                {"d": doc_id},
            ).fetchone()
            rows = con.execute(
                "SELECT text FROM chunks WHERE doc_id = :d AND strategy = :s ORDER BY ordinal",
                {"d": doc_id, "s": strategy[0] if strategy else ""},
            ).fetchall()
            out[cid] = ("ok", "\n".join(str(r[0]) for r in rows))
    finally:
        con.close()
    return out
