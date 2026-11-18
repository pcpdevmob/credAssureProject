"""Cited passages (UI-06): the text behind a citation, read-only, scoped to the case.

The same ADR 0019 filter that governed the answer governs this read (`Searcher.passage`), so a
passage that was not in force for the case, another case's KFS or another tenant's document is a
404 with one message for every cause: the route never confirms that a document exists (SUP-08).
The text is data (BR-15): it is returned as plain text, scanned for injection, never as HTML.
Only legal bases L1 (open data), L2 (Gazette matter) and L5 (team-owned) are shown in full.
Every other basis, L3 and L4 included, and an unknown or missing one, is limited to a 600
character excerpt."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from fastapi import Path as PathParam
from pydantic import BaseModel

from credassure.core.errors import ApiErrorCode
from credassure.gateway.deps import Svc, User, visible_case
from credassure.gateway.problems import ProblemError
from credassure.guardrails.events import record as guardrail
from credassure.guardrails.excerpt import EXCERPT_LIMIT, FULL_TEXT_BASES, excerpt
from credassure.guardrails.switch import on as rail_on
from credassure.ledger import reads
from credassure.ledger.session import transaction
from credassure.retrieval.search import Filters, Searcher
from credassure.security.injection import scan

router = APIRouter(prefix="/v1", tags=["cases"])


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
    truncated: bool  # True when the text is a 600 character excerpt (legal basis not L1, L2 or L5)
    injection_flagged: bool
    injection_flags: list[str]


@router.get("/cases/{case_id}/citations/{chunk_id:path}", response_model=CitationPassage)
def citation(
    case_id: Annotated[str, PathParam(min_length=1, max_length=32)],
    chunk_id: Annotated[str, PathParam(min_length=1, max_length=160)],
    who: User,
    svc: Svc,
    quote: Annotated[str | None, Query(max_length=1000)] = None,
) -> CitationPassage:
    case = visible_case(svc, who, case_id)  # 404 for a case this caller cannot see
    with transaction(svc.engine) as s:
        own = reads.own_kfs(s, case.tenant_id, case.id)
    return _passage(svc, case.id, case.tenant_id, own, chunk_id, quote)


@router.get("/citations/{chunk_id:path}", response_model=CitationPassage)
def citation_outside_a_case(
    chunk_id: Annotated[str, PathParam(min_length=1, max_length=160)],
    who: User,
    svc: Svc,
    quote: Annotated[str | None, Query(max_length=1000)] = None,
) -> CitationPassage:
    """A passage cited by an answer given outside a case (ADR 0035): the same filter with no
    case, so every case's KFS is a 404 here."""
    return _passage(svc, None, who.tenant_id, frozenset(), chunk_id, quote)


def _passage(
    svc: Svc,
    case_id: str | None,
    tenant_id: str,
    own: frozenset[str],
    chunk_id: str,
    quote: str | None,
) -> CitationPassage:
    settings = svc.settings
    found = None
    if settings.corpus_db.exists():
        filters = Filters(as_of=settings.as_of_date, home_state=settings.home_state, own_kfs=own)
        found = Searcher(settings.corpus_db, None, None, tenant_id=tenant_id).passage(
            chunk_id, case_id, tenant_id, filters
        )
    if found is None:
        raise ProblemError(404, "no such passage for this case", ApiErrorCode.NOT_FOUND)
    short = (  # R2 excerpt cap; off only under the A6 ablation (guardrails.switch)
        rail_on("R2")
        and found.legal_basis not in FULL_TEXT_BASES
        and len(found.text) > EXCERPT_LIMIT
    )
    text = excerpt(found.text, quote) if short else found.text
    flags = scan(text)
    # ADR 0029 R2: a read, so the events stay in the trace (no audit row per citation view)
    if short:
        guardrail("R2", "R2.citation_excerpt_capped", "cap", case_id=case_id, chunk_id=chunk_id)
    if flags:
        guardrail("R2", "R2.passage_injection_flagged", "flag", case_id=case_id, flags=flags)
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
