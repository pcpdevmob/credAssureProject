"""Fact lineage (scope #33, OBJ-08): where one figure came from — engine, inputs, sources, who
wrote it and when. Read-only; same tenant and case checks as every case route (SUP-08). Agent
ledger-prefix rules (#24) govern what agents may touch, not what a case member may read."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi import Path as PathParam
from pydantic import BaseModel
from sqlalchemy import Engine

from credassure.core.errors import ApiErrorCode
from credassure.core.money import to_paise
from credassure.gateway.deps import Svc, User, visible_case
from credassure.gateway.problems import ProblemError
from credassure.gateway.routers.cases import money
from credassure.ledger import reads
from credassure.ledger.session import hr_engine, transaction

router = APIRouter(prefix="/v1", tags=["cases"])


class FactValue(BaseModel):
    text: str
    paise: int | None  # INR facts only
    display: str


class EngineRef(BaseModel):
    name: str
    version: str | None


class SourceFile(BaseModel):
    kind: str
    name: str  # the upload label the producer cited (original filenames are not stored)
    sha256: str
    uploaded_at: datetime


class Input(BaseModel):
    kind: str  # fact | hr_record | ref
    ref: str
    fact_key: str | None


class Passage(BaseModel):
    doc_id: str
    title: str | None
    section: str | None
    chunk_id: str | None


class Producer(BaseModel):
    agent: str | None
    stage: str | None
    trace_id: str | None


class AuditRef(BaseModel):
    seq: int
    actor: str
    ts: str


class Lineage(BaseModel):
    case_id: str
    key: str
    version: int
    latest_version: int
    superseded_by: int | None
    value: FactValue
    unit: str
    created_at: datetime
    source_type: str
    source_ref: str
    engine: EngineRef
    input_hash: str
    files: list[SourceFile]
    inputs: list[Input]
    passages: list[Passage]
    producer: Producer
    audit: AuditRef | None


def _kind(label: str) -> str:
    return label.partition(":")[0]  # "offer:OF-01-A.v1" -> "offer"; "order" -> "order"


@lru_cache(maxsize=4)
def _corpus(path: Path) -> Engine:
    return hr_engine(path)  # read-only SQLite engine (mode=ro, query_only)


@router.get("/cases/{case_id}/facts/{key}/lineage", response_model=Lineage)
def lineage(
    case_id: str,
    key: Annotated[str, PathParam(max_length=128, pattern=r"^[A-Za-z0-9_.:\-]+$")],
    who: User,
    svc: Svc,
    version: Annotated[int | None, Query(ge=1, le=2**31 - 1)] = None,
) -> Lineage:
    case = visible_case(svc, who, case_id)
    with transaction(svc.engine) as s:
        fact = reads.get_fact(s, case.tenant_id, case.id, key, version)
        latest = reads.get_latest(s, case.tenant_id, case.id, key)
        if fact is None or latest is None:
            raise ProblemError(404, f"no fact {key} on case {case_id}", ApiErrorCode.NOT_FOUND)
        event = reads.fact_event(s, case.tenant_id, case.id, key, fact.version)
        files = reads.case_files(s, case.tenant_id, case.id)
        keys = {f.key for f in reads.list_for_case(s, case.tenant_id, case.id)}

    tokens = [t.strip() for t in fact.source_ref.split(",") if t.strip()]
    found: list[SourceFile] = []
    inputs: list[Input] = []
    loose: list[str] = []
    for token in tokens:
        if token.startswith("case_files:"):
            token = token.removeprefix("case_files:")
        label, _, sha12 = token.rpartition("@")
        row = (
            next((f for f in files if f.sha256.startswith(sha12) and _kind(label) == f.kind), None)
            if label and len(sha12) >= 12
            else None
        )
        if row is not None:
            found.append(
                SourceFile(kind=row.kind, name=label, sha256=row.sha256, uploaded_at=row.created_at)
            )
        elif token.startswith("hr.db:"):
            inputs.append(Input(kind="hr_record", ref=token, fact_key=None))
        elif token in keys:
            inputs.append(Input(kind="fact", ref=token, fact_key=token))
        else:
            loose.append(token)

    # One rule in every environment: a resolved corpus id, or any token of a `reference` fact, is a
    # passage; the corpus only fills in title and section when it is ingested.
    refs: dict[str, tuple[str, str, str | None, str | None]] = {}
    if loose and svc.settings.corpus_db.exists():
        with transaction(svc.engine) as s:
            own = reads.own_kfs(s, case.tenant_id, case.id)
        with transaction(_corpus(svc.settings.corpus_db)) as s:
            refs = reads.corpus_refs(s, loose, case.tenant_id, case.id, own)
    passages = [
        Passage(doc_id=d, title=t, section=sec, chunk_id=c)
        for d, t, sec, c in (
            refs.get(x, (x, None, None, None))
            for x in loose
            if x in refs or fact.source_type == "reference"
        )
    ]
    inputs += [
        Input(kind="ref", ref=x, fact_key=None)
        for x in loose
        if x not in refs and fact.source_type != "reference"
    ]

    paise = None
    if fact.unit == "INR":
        try:
            paise = to_paise(Decimal(fact.value_text))
        except InvalidOperation:
            paise = None
    name, _, engine_version = fact.produced_by.partition("@")
    payload = event.payload if event is not None else {}
    return Lineage(
        case_id=case.id,
        key=fact.key,
        version=fact.version,
        latest_version=latest.version,
        superseded_by=latest.version if latest.version > fact.version else None,
        value=FactValue(
            text=fact.value_text,
            paise=paise,
            display=money(paise)["display"] if paise is not None else fact.value_text,
        ),
        unit=fact.unit,
        created_at=fact.created_at,
        source_type=fact.source_type,
        source_ref=fact.source_ref,
        engine=EngineRef(name=name, version=engine_version or None),
        input_hash=fact.input_hash,
        files=found,
        inputs=inputs,
        passages=passages,
        producer=Producer(
            agent=payload.get("agent"), stage=payload.get("stage"), trace_id=payload.get("trace_id")
        ),
        audit=AuditRef(seq=event.seq, actor=event.actor, ts=event.ts)
        if event is not None
        else None,
    )
