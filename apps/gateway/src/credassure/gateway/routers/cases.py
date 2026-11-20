"""Cases, uploads and case views (UI-01..06, UI-08, API-01, OBJ-08).

Money leaves as {paise, display} (ADR 0004). Every read is tenant- and case-scoped (SUP-08).
"""

import csv
import hashlib
import html
import io
import json
import math
import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, get_args

import yaml
from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationError

from credassure.core import narrative
from credassure.core.enums import Stage
from credassure.core.errors import ApiErrorCode
from credassure.core.money import format_inr, from_paise, to_paise
from credassure.core.schemas import (
    CostRow,
    InventoryRow,
    OfferUpload,
    OpeningPosition,
    OrderFile,
    PayableRow,
    ReceiptRow,
    ReceivableRow,
)
from credassure.core.schemas.offer import KFS_DOC_ID, OFFER_ID
from credassure.engines.normaliser import parse_money
from credassure.gateway import report
from credassure.gateway.deps import Svc, User, case_ref, own_case, role, visible_case
from credassure.gateway.problems import ProblemError
from credassure.guardrails.events import AuditSink
from credassure.guardrails.events import record as guardrail
from credassure.guardrails.policy import load as guardrail_policy
from credassure.guardrails.protected import find as find_protected
from credassure.guardrails.switch import on as rail_on
from credassure.ledger import reads
from credassure.ledger.models import Case
from credassure.ledger.session import run_in_progress, run_lock, transaction
from credassure.security.auth import Principal, Role, can_view_case
from credassure.security.injection import scan
from credassure.security.pii import find as pii_find

router = APIRouter(prefix="/v1", tags=["cases"])

FileKind = Literal[
    "order",
    "opening_position",
    "costs",
    "receipts",
    "receivables",
    "payables",
    "inventory",
    "offer",  # one lender offer version per file (LW-01)
    "kfs",  # a KFS or schedule of charges, Markdown with frontmatter (LW-04)
]
_SCHEMAS: dict[str, type[BaseModel]] = {
    "order": OrderFile,
    "opening_position": OpeningPosition,
    "costs": CostRow,
    "receipts": ReceiptRow,
    "receivables": ReceivableRow,
    "payables": PayableRow,
    "inventory": InventoryRow,
    "offer": OfferUpload,
}
_JSON_KINDS = frozenset({"order", "opening_position", "offer"})
_KFS_ID, _OFFER_ID = re.compile(KFS_DOC_ID), re.compile(OFFER_ID)
_LOCKED = frozenset({"AWAITING_APPROVAL", "HELD", "APPROVED", "REJECTED"})


MAX_PAISE = 10**15  # ₹1,00,00,00,00,00,000: far above any MSME order; fits SQLite INTEGER (#51)
MAX_INT = 2**31 - 1  # versions and counters (same bound as the lineage route)


def money(paise: int) -> dict[str, Any]:
    return {"paise": paise, "display": format_inr(from_paise(paise))}


class NewCase(BaseModel):
    msme_name: str = Field(min_length=1, max_length=200)
    order_ref: str = Field(min_length=1, max_length=64)
    order_value_paise: int = Field(gt=0, le=MAX_PAISE)
    indicative_amount_paise: int = Field(ge=0, le=MAX_PAISE)
    due_date: date


def _summary(case: Case) -> dict[str, Any]:
    return {
        "case_id": case.id,
        "msme_name": case.msme_name,
        "order_ref": case.order_ref,
        "status": case.status,
        "current_stage": case.current_stage,
        "route": case.route,
        "row_version": case.row_version,
        "order_value": money(case.order_value_paise),
        "indicative_amount": money(case.indicative_amount_paise),  # UI-01: never the result
        "due_date": case.due_date.isoformat(),
    }


_NEXT_ACTION = {
    "CREATED": "Upload the case files, then run the workflow.",
    "PAUSED": "Answer the question, correct the data, then run again.",
    "FAILED": "A stage failed; an evaluator can inspect the trace and retry.",
    "RETURNED": "The approver returned the case; fix the named stage and run again.",
    "AWAITING_APPROVAL": "Waiting for the routed approver.",
    "HELD": "Held at exactly ₹1.5 crore; waiting for the VP (APR-03).",
    "APPROVED": "Approved internally. The MSME chooses its lender outside the system.",
    "REJECTED": "Rejected.",
}


NARRATIVE_PREFIX = {"onboarding": "onb.", "working_capital": "wc.", "lendwise": "lw."}


def _narrative_source(svc: Svc, case: Case, stage: str) -> str | None:
    """P9 AI badge: "model" when the stage narrative is model-drafted, "template" when code wrote
    it (fallback or model off), None when the stage has no stored narrative."""
    prefix = NARRATIVE_PREFIX.get(stage)
    raw = svc.ledger.get(case.id, f"{prefix}narrative") if prefix else None
    parsed = narrative.parse(raw)
    if parsed is None:
        return None
    return "model" if parsed[1] else "template"


def _stage_views(svc: Svc, case: Case) -> list[dict[str, Any]]:
    with transaction(svc.engine) as s:
        runs = reads.stage_runs(s, case.tenant_id, case.id)
    latest: dict[str, Any] = {}
    for run in runs:  # oldest first, so the newest attempt per stage wins
        result = json.loads(run.result_json) if run.result_json else {}
        latest[run.stage] = {
            "stage": run.stage,
            "decision": run.decision,
            "attempt": run.attempt,
            "blockers": result.get("blockers", []),
            "question": result.get("question"),
            "narrative": result.get("narrative"),
            "narrative_source": _narrative_source(svc, case, run.stage),
            "trace_id": run.trace_id,
        }
    order = [s.value for s in Stage]
    return sorted(latest.values(), key=lambda v: order.index(v["stage"]))


Preparer = Annotated[Principal, role(Role.PREPARER)]
Evaluator = Annotated[Principal, role(Role.EVALUATOR)]


@router.post("/cases", status_code=201)
def create_case(body: NewCase, who: Preparer, svc: Svc) -> dict[str, Any]:
    case = svc.ledger.create_case(
        year=datetime.now(UTC).year,
        msme_name=body.msme_name,
        order_ref=body.order_ref,
        order_value_paise=body.order_value_paise,
        indicative_amount_paise=body.indicative_amount_paise,
        due_date=body.due_date,
        preparer_id=who.user_id,
    )
    return _summary(case)


def _recommended(s: Any, case: Case) -> int | None:
    """Validated need in paise; None until the latest WC gate is GO (NEEDS_INPUT makes it stale)."""
    gate = reads.get_latest(s, case.tenant_id, case.id, "wc.gate")
    amount = reads.get_latest(s, case.tenant_id, case.id, "wc.recommended_amount")
    if gate is None or gate.value_text != "GO" or amount is None:
        return None
    return to_paise(Decimal(amount.value_text))


def _with_need(s: Any, case: Case) -> dict[str, Any]:
    need = _recommended(s, case)
    return {**_summary(case), "recommended_amount": money(need) if need is not None else None}


@router.get("/cases")
def list_cases(who: User, svc: Svc) -> dict[str, Any]:
    """Cases plus dashboard totals, summed here in integer paise so no client adds money (BR-05)."""
    # ponytail: two fact reads per case; one grouped query if the list grows past a few hundred.
    with transaction(svc.engine) as s:
        items = [
            _with_need(s, c)
            for c in reads.list_cases(s, who.tenant_id)
            if can_view_case(who, case_ref(c))
        ]
    done = [i for i in items if i["recommended_amount"]]
    need = sum(i["recommended_amount"]["paise"] for i in done)
    asked = sum(i["indicative_amount"]["paise"] for i in done)
    totals = {
        "validated_cases": len(done),
        "validated_need": money(need),
        "requested_for_validated": money(asked),
        "over_borrowing_avoided": money(asked - need),
    }
    return {"items": items, "totals": totals}


@router.get("/cases/{case_id}")
def get_case(case_id: str, who: User, svc: Svc) -> dict[str, Any]:
    case = visible_case(svc, who, case_id)
    stages = _stage_views(svc, case)
    paused = next((v for v in stages if v["decision"] not in ("GO", None)), None)
    with transaction(svc.engine) as s:
        head = _with_need(s, case)
    return {
        **head,
        "stages": stages,
        "question": paused["question"] if paused and case.status == "PAUSED" else None,
        "next_action": _NEXT_ACTION.get(case.status, ""),
    }


# ---- uploads (UI-02) ---------------------------------------------------------------------------
def _cell(model: type[BaseModel], column: str, value: str) -> Any:
    """Money cells may use Indian formats (DATA_SPEC §2): normalise them with the VER-01 parser."""
    field = model.model_fields.get(column)
    if field is not None and Decimal in (field.annotation, *get_args(field.annotation)):
        try:
            return parse_money(value.strip()).value
        except ValueError:
            return value  # pydantic reports it with field and row
    return value


FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")  # S7: spreadsheet formula injection
MONEY_LIMIT = Decimal(10) ** 11  # S8: ₹10^11 (10^13 paise) is far above any MSME figure


def _hostile(value: Any, path: str = "") -> list[dict[str, Any]]:
    """S7/S8: formula-like text and non-finite or absurd money, anywhere in a validated payload."""
    if isinstance(value, BaseModel):
        value = dict(value)
    if isinstance(value, dict):
        return [e for k, v in value.items() for e in _hostile(v, f"{path}.{k}".strip("."))]
    if isinstance(value, list):
        return [e for i, v in enumerate(value) for e in _hostile(v, f"{path}.{i}")]
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES) and not _is_number(value):
        return [{"field": path, "row": None, "reason": "text may not start with = + - @"}]
    if isinstance(value, Decimal | float) and (
        not math.isfinite(value) or abs(Decimal(value)) > MONEY_LIMIT
    ):
        return [{"field": path, "row": None, "reason": "amount is not finite or out of range"}]
    if isinstance(value, Decimal) and "E" in str(value).upper():  # "1E+7": engines refuse it
        return [{"field": path, "row": None, "reason": "write the amount in plain digits"}]
    return []


def _is_number(text: str) -> bool:
    try:
        return math.isfinite(float(text))
    except ValueError:
        return False


def _validated(model: type[BaseModel], data: Any, row: int | None) -> dict[str, Any]:
    """Validate, then reject hostile values; errors carry field and row (UI-02)."""
    parsed = model.model_validate(data)
    bad = _hostile(parsed)
    if bad:
        raise ProblemError(422, "file failed validation", errors=[{**e, "row": row} for e in bad])
    # None = absent: the WC validator then names the missing field (WC-01)
    out: dict[str, Any] = parsed.model_dump(mode="json", exclude_none=True)
    return out


def _errors(exc: ValidationError, row: int | None) -> list[dict[str, Any]]:
    return [
        {"field": ".".join(str(p) for p in e["loc"]) or None, "row": row, "reason": e["msg"]}
        for e in exc.errors()
    ]


def _kfs(text: str) -> dict[str, Any]:
    """KFS Markdown: frontmatter names the document; the body is stored as data only (BR-15)."""
    head, sep, body = text.removeprefix("---\n").partition("\n---\n")
    try:
        meta = yaml.safe_load(head) if text.startswith("---\n") and sep else None
    except yaml.YAMLError:
        meta = None
    meta = meta if isinstance(meta, dict) else {}
    doc_id = meta.get("doc_id")
    if not isinstance(doc_id, str) or not _KFS_ID.match(doc_id):
        raise ProblemError(
            422,
            "kfs failed validation",
            errors=[{"field": "doc_id", "row": None, "reason": "frontmatter has no doc_id"}],
        )
    # Only plain short strings leave the frontmatter: a YAML alias bomb never gets stringified.
    oid, cid = meta.get("offer_id"), meta.get("case_id")
    return {
        "doc_id": doc_id,
        "offer_id": oid if isinstance(oid, str) and _OFFER_ID.match(oid) else "",
        "case_ref": cid if isinstance(cid, str) and len(cid) <= 32 else "",
        "text": body,
    }


def _parse(kind: str, text: str) -> tuple[Any, int]:
    if kind == "kfs":
        return _kfs(text), 1
    model = _SCHEMAS[kind]
    if kind in _JSON_KINDS:
        try:
            data = json.loads(text, parse_float=Decimal)  # rates and money are never float
        except (json.JSONDecodeError, RecursionError) as exc:  # N3: deep nesting is bad input
            reason = exc.msg if isinstance(exc, json.JSONDecodeError) else "nested too deeply"
            raise ProblemError(
                422,
                "file is not valid JSON",
                errors=[{"field": None, "row": None, "reason": reason}],
            ) from exc
        try:
            return _validated(model, data, None), 1
        except ValidationError as exc:
            raise ProblemError(422, f"{kind} failed validation", errors=_errors(exc, None)) from exc
    reader = csv.DictReader(io.StringIO(text))
    missing = [
        name
        for name, f in model.model_fields.items()
        if f.is_required() and name not in (reader.fieldnames or [])
    ]
    if missing:
        cols = [{"field": m, "row": None, "reason": "missing column"} for m in missing]
        raise ProblemError(422, f"{kind} is missing columns", errors=cols)
    rows: list[Any] = []
    errors: list[dict[str, Any]] = []
    try:
        for number, raw in enumerate(reader, start=1):
            cleaned = {k: _cell(model, k, v or "") for k, v in raw.items() if k is not None}
            try:
                rows.append(_validated(model, cleaned, number))
            except ValidationError as exc:
                errors.extend(_errors(exc, number))
            except ProblemError as exc:
                errors.extend(exc.errors or [])
    except csv.Error as exc:  # N3: malformed CSV (e.g. a field over the parser limit)
        errors.append({"field": None, "row": reader.line_num, "reason": f"bad CSV: {exc}"})
    if errors:
        raise ProblemError(422, f"{kind} failed validation", errors=errors[:100])
    if not rows:
        raise ProblemError(
            422, f"{kind} has no rows", errors=[{"field": None, "row": None, "reason": "empty"}]
        )
    return rows, len(rows)


def validate_file(
    kind: str, text: str, *, case_id: str | None = None, audit: AuditSink | None = None
) -> tuple[Any, int]:
    """Everything an upload checks about the file text itself (UI-02, NFR-07); also used by
    scripts/case_xlsx.py so authored files are validated by exactly this code."""
    # NFR-07: personal identifiers are refused, never stored. IFSC, phone and email are not
    # checked here: the IFSC shape matches ordinary IDs (see guardrails.pii).
    refuse = guardrail_policy().refuse_pii_kinds if rail_on("R1") else frozenset()  # A6
    ids = [h for h in pii_find(text) if h.kind in refuse]
    if ids:  # ADR 0029 R1: a block, audited with the kinds and count only, never the text
        guardrail(
            "R1",
            "R1.upload_pii_refused",
            "block",
            case_id=case_id,
            audit=audit,
            file_kind=kind,
            kinds=sorted({h.kind for h in ids}),
            count=len(ids),
        )
        raise ProblemError(
            422,
            f"{kind} contains a personal identifier",
            errors=[
                {
                    "field": None,
                    "row": text.count("\n", 0, h.start) + 1,
                    "reason": f"{h.kind} number not allowed in case files",
                }
                for h in ids[:20]
            ],
        )
    # P8.3 scope #67: no protected-attribute field reaches a gate or prompt (R1; A6 turns it off)
    if kind != "kfs" and rail_on("R1"):
        protected = find_protected(text, is_json=kind in _JSON_KINDS)
        if protected:
            guardrail(
                "R1",
                "R1.upload_protected_attribute",
                "block",
                case_id=case_id,
                audit=audit,
                file_kind=kind,
                fields=[f[:64] for f in protected[:20]],
                count=len(protected),
            )
            raise ProblemError(
                422,
                f"{kind} contains a protected-attribute field",
                errors=[
                    {
                        "field": f[:64],
                        "row": None,
                        "reason": "protected attributes are not used and not accepted",
                    }
                    for f in protected[:20]
                ],
            )
    return _parse(kind, text)


@router.post("/cases/{case_id}/files", status_code=201)
async def upload(
    request: Request,
    case_id: str,
    kind: Annotated[FileKind, Query()],
    file: Annotated[UploadFile, File()],
    who: User,
    svc: Svc,
) -> dict[str, Any]:
    case = own_case(svc, who, case_id)
    if case.status in _LOCKED:
        raise ProblemError(409, f"case is {case.status}; inputs are locked", ApiErrorCode.CONFLICT)
    if run_in_progress(svc.engine, case.id):  # S10: inputs never change under a running stage
        raise ProblemError(409, "a run is in progress on this case", ApiErrorCode.RUN_IN_PROGRESS)
    limit = svc.settings.max_upload_bytes
    declared = request.headers.get("content-length", "")
    # S3: early 413. ponytail: FastAPI has already parsed the multipart body by now; an ASGI
    # guard that stops reading at the limit is E10 SHOULD-1 (deferred, see PROGRESS).
    if declared.isdigit() and int(declared) > limit + 64 * 1024:
        raise ProblemError(
            413, f"file is larger than {limit} bytes", ApiErrorCode.PAYLOAD_TOO_LARGE
        )
    suffix = "json" if kind in _JSON_KINDS else "md" if kind == "kfs" else "csv"
    name = (file.filename or "").lower()
    allowed = {
        "json": {"application/json"},
        "csv": {"text/csv", "application/csv"},
        "md": {"text/markdown", "text/plain", "text/x-markdown"},
    }[suffix]
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if not name.endswith(f".{suffix}") or content_type not in {
        *allowed,
        "application/octet-stream",
    }:
        raise ProblemError(
            415, f"{kind} must be a .{suffix} file", ApiErrorCode.UNSUPPORTED_MEDIA_TYPE
        )
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise ProblemError(
            413, f"file is larger than {limit} bytes", ApiErrorCode.PAYLOAD_TOO_LARGE
        )
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProblemError(
            415, "file is not UTF-8 text", ApiErrorCode.UNSUPPORTED_MEDIA_TYPE
        ) from exc
    payload, count = validate_file(kind, text, case_id=case.id, audit=svc.ledger.audit)
    # BR-15: uploads are data. A hit is flagged and audited; nothing in the file is obeyed.
    flags = scan(text)
    if kind == "kfs" and payload["case_ref"] not in ("", case.id):
        flags.append("KFS_CASE_MISMATCH")  # the document names another case: recorded, kept
    stored = svc.ledger.store_case_file(
        case.id, kind, json.dumps(payload), who.user_id, sha256=hashlib.sha256(raw).hexdigest()
    )
    if flags:
        svc.ledger.audit(
            case.id, "INJECTION_FLAGGED", {"kind": kind, "sha256": stored.sha256, "flags": flags}
        )
        for rule, hit in (
            ("R1.upload_case_mismatch", [f for f in flags if f == "KFS_CASE_MISMATCH"]),
            ("R1.upload_injection_flagged", [f for f in flags if f != "KFS_CASE_MISMATCH"]),
        ):
            if hit:  # audited above as INJECTION_FLAGGED; the span names that event
                guardrail(
                    "R1", rule, "flag", case_id=case.id, flags=hit, audited_as="INJECTION_FLAGGED"
                )
    return {"kind": kind, "sha256": stored.sha256, "rows": count, "injection_flags": flags}


# ---- views -------------------------------------------------------------------------------------
def _facts(svc: Svc, case: Case, prefix: str) -> list[dict[str, Any]]:
    with transaction(svc.engine) as s:
        facts = reads.list_for_case(s, case.tenant_id, case.id)
    latest = {f.key: f for f in facts if f.key.startswith(prefix)}  # versions ascend per key
    return [
        {
            "key": f.key,
            "value": f.value_text,
            "unit": f.unit,
            "version": f.version,
            "source_type": f.source_type,
        }
        for f in latest.values()
    ]


@router.get("/cases/{case_id}/funding")
def funding(case_id: str, who: User, svc: Svc) -> dict[str, Any]:
    case = visible_case(svc, who, case_id)
    facts = _facts(svc, case, "wc.")
    with transaction(svc.engine) as s:
        need = _recommended(s, case)
    return {
        "recommended_amount": money(need) if need is not None else None,
        "indicative_amount": money(case.indicative_amount_paise),
        "facts": facts,
    }


@router.get("/cases/{case_id}/offers")
def offers(case_id: str, who: User, svc: Svc) -> dict[str, Any]:
    """The offer comparison (UI-05): stored lw.* facts after the LendWise stage, else a
    read-only audit preview (no affordability, no ranking)."""
    result: dict[str, Any] = svc.service.offers(who, case_id)
    return result


class Chat(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@router.post("/cases/{case_id}/chat")
def chat(case_id: str, body: Chat, who: User, svc: Svc) -> dict[str, Any]:
    reply: dict[str, Any] = svc.service.chat(who, case_id, body.message)
    return reply


REPORT_HEADERS = {  # N7: a stored report can never run script or be sniffed as another type
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
}


@router.get("/cases/{case_id}/report", response_model=None)
def get_report(
    case_id: str,
    who: User,
    svc: Svc,
    fmt: Annotated[Literal["md", "html", "json"], Query()] = "md",
    version: Annotated[int | None, Query(ge=1, le=MAX_INT)] = None,
) -> PlainTextResponse | dict[str, Any]:
    """The proposal report (UI-08) at `version` (default: latest; a draft when none exists).
    Rendered from the ledger fact versions it pinned; `stale` when the figures changed since
    (scope #6). `fmt=json` gives each section's text with its figures' ledger keys (#33)."""
    case = visible_case(svc, who, case_id)
    with transaction(svc.engine) as s:
        found = report.render(s, case, version)
    if found is None:
        raise ProblemError(404, f"no report version {version}", ApiErrorCode.NOT_FOUND)
    if fmt == "json":
        return found
    text = report.markdown(found)
    headers = {**REPORT_HEADERS, "X-Report-Stale": str(found["stale"]).lower()}
    if fmt == "html":
        return PlainTextResponse(
            f"<!doctype html><meta charset='utf-8'><pre>{html.escape(text)}</pre>",
            media_type="text/html",
            headers=headers,
        )
    return PlainTextResponse(text, media_type="text/markdown", headers=headers)


@router.post("/cases/{case_id}/report", status_code=201)
def new_report(case_id: str, who: User, svc: Svc) -> dict[str, Any]:
    """A new report version from the current figures (scope #6). The case preparer only. A
    report that is current keeps its version; one stale on an upload stays stale until the
    stage re-runs on the new file."""
    case = own_case(svc, who, case_id)
    report.snapshot(svc.engine, case, svc.ledger.put_fact)
    with transaction(svc.engine) as s:
        st = report.state(s, case)
    return {k: st[k] for k in ("version", "stale", "reasons")}


@router.delete("/cases/{case_id}")
def delete_case(
    case_id: str,
    who: Evaluator,
    svc: Svc,
    expected_version: Annotated[int, Query(ge=0, le=MAX_INT)],
) -> dict[str, Any]:
    """Scope #39, ADR 0025 (evaluator only): remove the case content, keep the append-only record
    (facts, approvals, audit) as a tombstone; the hash chain still verifies. Under the run lock,
    at the case version the caller saw."""
    case = visible_case(svc, who, case_id)
    with run_lock(svc.engine, case.tenant_id, case.id, f"delete-{uuid.uuid4().hex}"):
        removed = svc.ledger.delete_case(
            case.id, expected_version=expected_version, actor=who.user_id
        )
        if svc.settings.case_database_url is not None and svc.checkpointer is not None:
            # ADR 0039: LangGraph state lives beside MySQL, not in it; remove the thread there too.
            svc.checkpointer.delete_thread(f"{case.tenant_id}:{case.id}")
    return {"case_id": case.id, "status": "DELETED", "removed": removed}


# P9 safety panel (plan v3.4 §6): the guardrail and Critic events of one case. Payload keys are an
# allowlist of codes and counts; audit payloads never hold raw text or identifiers (ADR 0029).
SAFETY_EVENTS = {
    "GUARDRAIL_EVENT",
    "INJECTION_FLAGGED",
    "CRITIC_BLOCKED",
    "CRITIC_FALLBACK",
    "LLM_FALLBACK",
    "GATE_OVERRIDE",
}
SAFETY_KEYS: tuple[str, ...] = ("rail", "rule_id", "action", "kinds", "count", "flags", "fields")
SAFETY_KEYS += ("file_kind", "stage", "codes", "reason", "kind")


@router.get("/cases/{case_id}/safety")
def safety(case_id: str, who: User, svc: Svc) -> dict[str, Any]:
    """Blocks, redactions, injection flags, Critic blocks and fallbacks for a case member."""
    case = visible_case(svc, who, case_id)
    with transaction(svc.engine) as s:
        events = [
            e
            for e in reads.audit_events(s, case.tenant_id, case.id)
            if e.event_type in SAFETY_EVENTS
        ]
    rows: list[dict[str, Any]] = []
    for e in events:
        payload = e.payload or {}
        rows.append(
            {"seq": e.seq, "ts": e.ts, "event_type": e.event_type}
            | {k: payload[k] for k in SAFETY_KEYS if k in payload}
        )
    counts: dict[str, int] = {}
    for r in rows:
        key = str(r.get("action") or str(r["event_type"]).lower())
        counts[key] = counts.get(key, 0) + 1
    return {"case_id": case.id, "counts": counts, "events": rows}


@router.get("/cases/{case_id}/audit")
def audit(case_id: str, who: Evaluator, svc: Svc) -> dict[str, Any]:
    case = visible_case(svc, who, case_id, include_deleted=True)  # the tombstone stays auditable
    with transaction(svc.engine) as s:
        events = reads.audit_events(s, case.tenant_id, case.id)
        broken = reads.verify_chain(s, who.tenant_id)
    return {
        "events": [
            {"seq": e.seq, "event_type": e.event_type, "actor": e.actor, "ts": e.ts} for e in events
        ],
        "chain_ok": not broken,
        "broken": broken,
    }
