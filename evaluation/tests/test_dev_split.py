"""Retrieval dev split (plan v3.4 §8, ADR 0032): tuning data that never overlaps the frozen sets."""

import json
import re
from pathlib import Path
from typing import Any

import yaml

from credassure.evaluation.gold.data import REPO

DEV = REPO / "evaluation" / "retrieval" / "dev" / "queries.jsonl"
FROZEN = [
    REPO / "evaluation" / "retrieval" / "v1" / "queries.jsonl",
    REPO / "evaluation" / "retrieval" / "v1" / "queries.v1.1-silver.jsonl",
    REPO / "evaluation" / "retrieval" / "v1" / "queries.v1.1-silver-lenient.jsonl",
    REPO / "evaluation" / "testset" / "v1" / "items.jsonl",
]
AS_OF = "2026-11-15"


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _cited(row: dict[str, Any]) -> set[str]:
    gold = row.get("gold", row)
    out = set(gold.get("relevant_doc_ids") or []) | set(gold.get("must_not_cite") or [])
    out |= {s["doc_id"] for s in gold.get("relevant_sections") or []}
    return out


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


DEV_ROWS = _rows(DEV)


def test_KR05_dev_split_has_15_to_20_unique_labelled_queries() -> None:
    ids = [r["id"] for r in DEV_ROWS]
    assert 15 <= len(DEV_ROWS) <= 20
    assert len(set(ids)) == len(ids)
    assert all(re.fullmatch(r"D\d{2}", i) for i in ids)
    for row in DEV_ROWS:
        assert row["relevant_doc_ids"], row["id"]
        assert row["label_status"] in {"proposed", "confirmed"}, row["id"]
        assert {s["doc_id"] for s in row["relevant_sections"]} <= set(row["relevant_doc_ids"])


def test_KR05_dev_split_never_overlaps_the_frozen_sets() -> None:
    frozen_docs: set[str] = set()
    frozen_queries: set[str] = set()
    for path in FROZEN:
        for row in _rows(path):
            frozen_docs |= _cited(row)
            text = row.get("query") or row.get("input", {}).get("question")
            if text:
                frozen_queries.add(_norm(text))
    for row in DEV_ROWS:
        assert not (_cited(row) & frozen_docs), (row["id"], _cited(row) & frozen_docs)
        assert _norm(row["query"]) not in frozen_queries, row["id"]


def test_KR04_dev_split_targets_current_indian_documents() -> None:
    docs = {
        d["doc_id"]: d
        for d in yaml.safe_load(
            (REPO / "data" / "corpus" / "manifest.yaml").read_text(encoding="utf-8")
        )["documents"]
    }
    for row in DEV_ROWS:
        for doc_id in row["relevant_doc_ids"]:
            doc = docs[doc_id]
            assert doc["jurisdiction"] in {"IN", "IN-MH"}, doc_id
            assert not doc.get("superseded_by"), doc_id
            assert doc.get("applies_to") in {"commercial_bank", "all"}, doc_id
            assert str(doc.get("effective_from") or "") <= AS_OF, doc_id


def test_scope60_whole_document_labels_are_not_exact() -> None:
    """A whole-document label (empty section) with exact=true would match only passages before
    the first heading (retrieval_eval.label_match), silently zeroing section-level recall."""
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "retrieval" / "dev" / "queries.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        for s in json.loads(line)["relevant_sections"]:
            assert not (s["section_path"] == "" and s.get("exact")), s
