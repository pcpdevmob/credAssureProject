"""Cited passages (UI-06): the text behind a citation, read-only, scoped to the case.

The same ADR 0019 filter that governed the answer governs this read (`Searcher.passage`), so a
passage that was not in force for the case, another case's KFS or another tenant's document is a
404 with one message for every cause: the route never confirms that a document exists (SUP-08).
The text is data (BR-15): it is returned as plain text, scanned for injection, never as HTML.
Legal basis L3 (Acts reproduced under s.52(1)(q)(ii)) is limited to a 600 character excerpt."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi import Path as PathParam
from pydantic import BaseModel

from credassure.core.errors import ApiErrorCode
from credassure.gateway.deps import Svc, User, visible_case
from credassure.gateway.problems import ProblemError
from credassure.ledger import reads
from credassure.ledger.session import transaction
from credassure.retrieval.search import Filters, Searcher
from credassure.security.injection import scan

router = APIRouter(prefix="/v1", tags=["cases"])
L3_LIMIT = 600  # characters of an L3 passage that may be shown


class CitationPassage(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    section: str | None
    effective_from: date | None
    legal_basis: str | None
    source_url: str | None
    text: str  # display-only plain text: never render it as HTML
    text_format: Literal["plain"] = "plain"
    truncated: bool  # True when the text is a 600 character excerpt (legal basis L3)
    injection_flagged: bool
    injection_flags: list[str]


def excerpt(text: str, quote: str | None, limit: int = L3_LIMIT) -> str:
    """At most ``limit`` characters, centred on the longest word of ``quote`` found in the text
    (else the start). A window, not a summary: the characters are the source's own."""
    if len(text) <= limit:
        return text
    centre, lowered = 0, text.lower()
    words = {w for w in (quote or "").lower().split() if len(w) >= 4}
    for word in sorted(words, key=len, reverse=True):
        at = lowered.find(word)
        if at >= 0:
            centre = at + len(word) // 2
            break
    start = max(0, min(centre - limit // 2, len(text) - limit))
    return text[start : start + limit]


@router.get("/cases/{case_id}/citations/{chunk_id:path}", response_model=CitationPassage)
def citation(
    case_id: Annotated[str, PathParam(min_length=1, max_length=32)],
    chunk_id: Annotated[str, PathParam(min_length=1, max_length=160)],
    who: User,
    svc: Svc,
    quote: Annotated[str | None, Query(max_length=1000)] = None,
) -> CitationPassage:
    case = visible_case(svc, who, case_id)  # 404 for a case this caller cannot see
    settings = svc.settings
    found = None
    if settings.corpus_db.exists():
        with transaction(svc.engine) as s:
            own = reads.own_kfs(s, case.tenant_id, case.id)
        filters = Filters(as_of=settings.as_of_date, home_state=settings.home_state, own_kfs=own)
        found = Searcher(settings.corpus_db, None, None, tenant_id=case.tenant_id).passage(
            chunk_id, case.id, case.tenant_id, filters
        )
    if found is None:
        raise ProblemError(404, "no such passage for this case", ApiErrorCode.NOT_FOUND)
    short = found.legal_basis == "L3" and len(found.text) > L3_LIMIT
    text = excerpt(found.text, quote) if short else found.text
    flags = scan(text)
    return CitationPassage(
        chunk_id=found.chunk_id,
        doc_id=found.doc_id,
        title=found.title,
        section=found.section_path,
        effective_from=found.effective_from,
        legal_basis=found.legal_basis,
        source_url=found.source_url,
        text=text,
        truncated=short,
        injection_flagged=bool(flags),
        injection_flags=flags,
    )
