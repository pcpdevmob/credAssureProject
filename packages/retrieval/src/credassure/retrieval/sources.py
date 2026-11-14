"""Read the corpus as it is on disk.

Real documents come from the manifest + lock (ADR 0019); synthetic KFS and policy documents from
their front matter (DATA_SPEC §4-5). Only citable documents are read: real ones need status
ok/ok_manual and extracted text.
"""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from credassure.core.seeded import SEED_TENANT
from credassure.security.injection import scan

AVAILABLE = {"ok", "ok_manual"}


@dataclass(frozen=True)
class SourceDoc:
    doc_id: str
    title: str
    collection: str  # public | policy | kfs
    tag: str
    jurisdiction: str
    applies_to: str
    effective_from: date | None
    superseded_by: str | None
    legal_basis: str
    sha256: str
    text: str
    publisher: str | None = None
    source_url: str | None = None
    case_id: str | None = None
    tenant_id: str | None = None  # set with case_id: the KFS belongs to (tenant, case)
    raw_flags: tuple[str, ...] = ()  # injection hits in the raw text, before boilerplate removal

    @property
    def real(self) -> bool:
        return self.legal_basis != "L5"


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def strip_boilerplate(
    texts: dict[str, str], *, share: float = 0.3, min_docs: int = 5, max_len: int = 60
) -> dict[str, str]:
    """Drop short lines found in ≥`share` of one source's documents (site menus, footers).

    ponytail: line-frequency heuristic per source tag; use an HTML boilerplate remover if menus
    survive.
    """
    if len(texts) < min_docs:
        return texts
    seen: Counter[str] = Counter()
    for text in texts.values():
        seen.update({s for line in text.splitlines() if (s := line.strip()) and len(s) <= max_len})
    common = {line for line, n in seen.items() if n >= share * len(texts)}
    return {
        doc_id: "\n".join(line for line in text.splitlines() if line.strip() not in common)
        for doc_id, text in texts.items()
    }


def _front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    _, head, body = text.split("---", 2)
    return yaml.safe_load(head) or {}, body.lstrip()


def real_docs(corpus_dir: Path) -> list[SourceDoc]:
    manifest = yaml.safe_load((corpus_dir / "manifest.yaml").read_text(encoding="utf-8"))
    lock = json.loads((corpus_dir / "manifest.lock.json").read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for entry in manifest["documents"]:
        status = lock.get(entry["doc_id"], {})
        path = corpus_dir / "text" / f"{entry['doc_id']}.txt"
        if status.get("status") in AVAILABLE and path.exists():
            rows.append(entry | {"_lock": status, "_text": path.read_text(encoding="utf-8")})
    by_tag: dict[str, dict[str, str]] = defaultdict(dict)
    for row in rows:
        by_tag[row.get("tag", "")][row["doc_id"]] = row["_text"]
    cleaned = {k: v for texts in by_tag.values() for k, v in strip_boilerplate(texts).items()}
    return [
        SourceDoc(
            doc_id=r["doc_id"],
            title=r.get("title") or r["doc_id"],
            collection=r.get("collection", "public"),
            tag=r.get("tag", ""),
            jurisdiction=r.get("jurisdiction", "IN"),
            applies_to=r.get("applies_to", "all"),
            effective_from=_date(r.get("effective_from")),
            superseded_by=r.get("superseded_by"),
            legal_basis=r["legal_basis"],
            sha256=r["_lock"].get("text_sha256") or r["_lock"]["sha256"],
            text=cleaned[r["doc_id"]],
            publisher=r.get("publisher"),
            source_url=r.get("source_url"),
            raw_flags=tuple(scan(r["_text"])),  # stripped lines stay on record (BR-15)
        )
        for r in rows
    ]


def synthetic_docs(frozen_dir: Path) -> list[SourceDoc]:
    import hashlib

    out = []
    for path in sorted([*frozen_dir.glob("kfs/*.md"), *frozen_dir.glob("policies/*.md")]):
        raw = path.read_text(encoding="utf-8")
        meta, body = _front_matter(raw)
        title = meta.get("title") or next(
            (line.lstrip("# ").strip() for line in body.splitlines() if line.startswith("# ")),
            meta["doc_id"],
        )
        out.append(
            SourceDoc(
                doc_id=meta["doc_id"],
                title=str(title),
                collection=meta["collection"],
                tag=meta["collection"],
                jurisdiction=meta.get("jurisdiction") or "IN",
                applies_to=meta.get("applies_to") or "all",
                effective_from=_date(meta.get("effective_from")),
                superseded_by=meta.get("superseded_by"),
                legal_basis="L5",
                sha256=hashlib.sha256(raw.encode()).hexdigest(),
                text=body,
                publisher="CredAssure team (synthetic)",
                case_id=meta.get("case_id"),
                tenant_id=SEED_TENANT if meta.get("case_id") else None,
            )
        )
    return out


def load_corpus(repo: Path) -> list[SourceDoc]:
    return real_docs(repo / "data" / "corpus") + synthetic_docs(repo / "data" / "frozen" / "v1")
