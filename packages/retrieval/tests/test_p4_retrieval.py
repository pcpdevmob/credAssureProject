"""Plan v3.4 P4 (scope #61, #62, #63; KR-01..05, CP-02): contextual headers keep chunk_ids and text,
the glossary rewrite is deterministic, and the answerability gate abstains below its threshold."""

import sqlite3
from collections.abc import Callable
from datetime import date
from pathlib import Path

from credassure.ledger import migrate
from credassure.retrieval import context, glossary
from credassure.retrieval.index import index_version, ingest, open_chroma
from credassure.retrieval.search import Filters, Searcher
from credassure.retrieval.sources import SourceDoc

Embed = Callable[[list[str]], list[list[float]]]
AS_OF = date(2026, 11, 15)
TEXT = (
    "# Fees\nThe annual guarantee fee is charged on the guaranteed amount in year one.\n"
    "# Tenure\nTerm loans run up to seven years."
)


def _doc(doc_id: str = "R-CG-02") -> SourceDoc:
    return SourceDoc(
        doc_id=doc_id, title="CGTMSE AGF basis", collection="public", tag="t", jurisdiction="IN",
        applies_to="all", effective_from=date(2025, 4, 1), superseded_by=None, legal_basis="L4",
        sha256="sha-1", text=TEXT, publisher="CGTMSE",
    )  # fmt: skip


def _ingest(tmp: Path, embed: Embed, *, headers: bool, seen: list[str] | None = None) -> Path:
    db = tmp / "corpus.db"
    migrate.upgrade("corpus", db)

    def spy(texts: list[str]) -> list[list[float]]:
        if seen is not None:
            seen.extend(texts)
        return embed(texts)

    ingest(
        [_doc()], corpus_db=db, chroma=open_chroma(tmp / "chroma"), embed=spy,
        embed_model="hash", audit=lambda *a: None, contextual_headers=headers,
    )  # fmt: skip
    return db


def _chunks(db: Path) -> list[tuple[str, str]]:
    with sqlite3.connect(db) as c:
        return c.execute("SELECT chunk_id, text FROM chunks ORDER BY chunk_id").fetchall()


def test_scope61_header_is_deterministic_and_section_only() -> None:
    doc = _doc()
    assert context.header(doc, "Fees") == "CGTMSE · CGTMSE AGF basis · Fees · 2025-04-01"
    assert context.embed_text(doc, "section", "x", "Fees", on=True).startswith("CGTMSE · ")
    assert context.embed_text(doc, "fixed512", "x", "Fees", on=True) == "x"
    assert context.embed_text(doc, "section", "x", "Fees", on=False) == "x"


def test_scope61_headers_change_only_what_is_embedded_chunk_ids_and_text_stay(
    tmp_path: Path, embed: Embed
) -> None:
    before = _chunks(_ingest(tmp_path, embed, headers=False))
    seen: list[str] = []
    db = _ingest(tmp_path, embed, headers=True, seen=seen)  # one re-ingest, same store
    assert _chunks(db) == before  # same chunk_ids, same stored text
    assert any(t.startswith("CGTMSE · CGTMSE AGF basis · Fees") for t in seen)
    # every chunk id cited before the re-ingest still resolves through the citation read path
    searcher = Searcher(db, None, None)
    for chunk_id, _ in before:
        assert searcher.passage(chunk_id, None, None, Filters(as_of=AS_OF)) is not None


def test_scope61_toggling_headers_changes_the_index_version() -> None:
    doc = _doc()
    assert index_version(doc, "m") != index_version(doc, "m", headers=True)
    assert index_version(doc, "m", headers=True).endswith(context.CONTEXT_VERSION)


def test_scope62_glossary_rewrite_adds_missing_forms_both_ways() -> None:
    assert glossary.rewrite("What does the KFS show?") == (
        "What does the KFS show? (key facts statement; key fact statement)"
    )
    assert "APR" in glossary.rewrite("How is the annual percentage rate computed?")
    assert glossary.rewrite("Hello there") == "Hello there"  # no term: unchanged
    assert glossary.rewrite("MSME loans") == glossary.rewrite("MSME loans")  # deterministic
    assert "micro and small enterprises" not in glossary.rewrite("MSME loans")  # MSE ≠ MSME


def test_scope62_rewrite_reaches_search_but_the_reranker_sees_the_user_words(
    tmp_path: Path, embed: Embed
) -> None:
    db = _ingest(tmp_path, embed, headers=False)
    asked: list[str] = []

    def rerank(query: str, texts: list[str]) -> list[float]:
        asked.append(query)
        return [1.0] * len(texts)

    s = Searcher(db, open_chroma(tmp_path / "chroma"), embed, reranker=rerank, query_rewrite=True)
    s.search_knowledge("AGF basis", filters=Filters(as_of=AS_OF))
    assert asked == ["AGF basis"]


def test_scope63_answerability_gate_abstains_below_the_threshold(
    tmp_path: Path, embed: Embed
) -> None:
    db = _ingest(tmp_path, embed, headers=False)
    chroma = open_chroma(tmp_path / "chroma")

    def rerank(query: str, texts: list[str]) -> list[float]:
        return [0.9 if "guarantee" in query else 0.1 for _ in texts]

    gate = Searcher(db, chroma, embed, reranker=rerank, min_score=0.5)
    assert gate.search_knowledge("guarantee fee", filters=Filters(as_of=AS_OF))
    assert gate.search_knowledge("fee tenure", filters=Filters(as_of=AS_OF)) == []
    scored = gate.scored("fee tenure", filters=Filters(as_of=AS_OF))
    assert scored and all(score == 0.1 for _, score in scored)
    off = Searcher(db, chroma, embed, reranker=rerank)  # no threshold: unchanged behaviour
    assert off.search_knowledge("fee tenure", filters=Filters(as_of=AS_OF))
    unranked = Searcher(db, chroma, embed, min_score=0.5)  # no reranker: the gate does not apply
    assert unranked.search_knowledge("fee tenure", filters=Filters(as_of=AS_OF))


def test_scope63_score_only_keeps_the_hybrid_order_and_still_gates(
    tmp_path: Path, embed: Embed
) -> None:
    """P4 ladder decision: reranking cut dev recall@5 (17 -> 11/20), so RERANK_ORDER=false keeps
    the hybrid order while the gate still reads the best reranker score over all candidates."""
    db = _ingest(tmp_path, embed, headers=False)
    chroma = open_chroma(tmp_path / "chroma")

    def rerank(query: str, texts: list[str]) -> list[float]:
        base = 0.9 if "guarantee" in query else 0.1
        return [base + i / 1000 for i in range(len(texts))]  # would reverse the order if used

    hybrid = Searcher(db, chroma, embed)
    plain = [
        p.chunk_id for p in hybrid.search_knowledge("guarantee fee", filters=Filters(as_of=AS_OF))
    ]
    only = Searcher(db, chroma, embed, reranker=rerank, rerank_order=False, min_score=0.5)
    kept = only.search_knowledge("guarantee fee", filters=Filters(as_of=AS_OF))
    assert [p.chunk_id for p in kept] == plain  # same order as without a reranker
    assert only.search_knowledge("fee tenure", filters=Filters(as_of=AS_OF)) == []  # gate holds
    reordered = Searcher(db, chroma, embed, reranker=rerank)
    got = [
        p.chunk_id
        for p in reordered.search_knowledge("guarantee fee", filters=Filters(as_of=AS_OF))
    ]
    assert got != plain or len(plain) < 2
