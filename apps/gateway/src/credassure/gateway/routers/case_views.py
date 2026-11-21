"""Plain-language case views for every case member (UI-02, UI-03, OBJ-08; UI thread 20 Nov).

Read-only. Nothing here calculates a figure, decides a gate or writes a row: each route returns
what the ledger, the case files, the HR store (read-only, ONB-05) or the audit log already hold,
so a non-technical preparer or approver can see it without the evaluator's raw audit view.

- `GET /v1/cases/{id}/files`: the latest upload per case-file kind (data the preparer entered),
  plus one entry per offer and KFS document, so the web form can show and edit what is stored.
- `GET /v1/cases/{id}/readiness`: the preparer's HR summary and each readiness rule the
  Onboarding stage recorded (`onb.rule.*` facts), with the HR record that evidences it.
- `POST /v1/cases/{id}/workbook`: the case Excel workbook converted to the same JSON/CSV files and
  stored through the same upload path (ADR 0040); `GET /v1/templates/case.xlsx` serves the template.
- `GET /v1/cases/{id}/history`: the case's audit events with an allowlist of payload keys and the
  actor's display name (no hashes, no input hashes, no source refs). The hash-chain check stays on
  the evaluator's `/audit` route; `chain_ok` is repeated here as one yes/no for everyone.
"""

import hashlib
import io
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import Response
from openpyxl import load_workbook
from pydantic import BaseModel, Field
from sqlalchemy import Engine, select, text

from credassure.core.errors import ApiErrorCode
from credassure.core.schemas.offer import KFS_DOC_ID, OFFER_ID
from credassure.gateway import pdf_intake, workbook
from credassure.gateway.deps import Svc, User, own_case, visible_case
from credassure.gateway.problems import ProblemError
from credassure.gateway.routers.cases import store_upload
from credassure.ledger import reads
from credassure.ledger.models import User as UserRow
from credassure.ledger.session import hr_engine, run_in_progress, transaction

router = APIRouter(prefix="/v1", tags=["cases"])

CASE_FILE_KINDS = (
    "order",
    "opening_position",
    "costs",
    "receipts",
    "receivables",
    "payables",
    "inventory",
)
MAX_ROWS = 2000  # a case file never has more; a larger stored payload is summarised, not sent


def iso(value: datetime | str | None) -> str | None:
    """ISO-8601 with an explicit UTC offset (SQLite hands back naive UTC datetimes)."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()


# ---- files --------------------------------------------------------------------------------------
@router.get("/cases/{case_id}/files")
def files(case_id: str, who: User, svc: Svc) -> dict[str, Any]:
    """What the case holds now: the newest upload per kind (newest wins, as the stages read it)."""
    case = visible_case(svc, who, case_id)
    with transaction(svc.engine) as s:
        rows = reads.case_files(s, case.tenant_id, case.id)  # ascending id: newest wins
    latest: dict[str, Any] = {}
    documents: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.kind in CASE_FILE_KINDS:
            latest[r.kind] = r
            continue
        payload = json.loads(r.payload_json)
        if r.kind == "offer":
            key = f"offer:{payload.get('offer_id', '')}.v{payload.get('version', '')}"
            label = f"{payload.get('lender_name') or payload.get('lender_id', '')}".strip()
            name = f"Offer {payload.get('offer_id', '')} (version {payload.get('version', '')})"
        else:  # kfs: the body is lender text (data only, BR-15) and is never sent back here
            key = f"kfs:{payload.get('doc_id', '')}"
            label = str(payload.get("offer_id") or "")
            name = f"Key Facts Statement {payload.get('doc_id', '')}"
        documents[key] = {
            "kind": r.kind,
            "name": name,
            "detail": label,
            "uploaded_at": iso(r.created_at),
        }
    out = []
    for kind in CASE_FILE_KINDS:
        if kind not in latest:
            out.append({"kind": kind, "uploaded_at": None, "rows": 0, "data": None})
            continue
        r = latest[kind]
        data = json.loads(r.payload_json)
        count = len(data) if isinstance(data, list) else 1
        out.append(
            {
                "kind": kind,
                "uploaded_at": iso(r.created_at),
                "rows": count,
                "data": data if count <= MAX_ROWS else None,
            }
        )
    return {"case_id": case.id, "files": out, "documents": list(documents.values())}


# ---- readiness ----------------------------------------------------------------------------------
@lru_cache(maxsize=4)
def _hr(path: Path) -> Engine:
    return hr_engine(path)


def _employee(svc: Svc, emp_id: str) -> dict[str, Any] | None:
    """Display fields and the records behind each readiness rule; SELECT only (ONB-05)."""
    with _hr(svc.settings.hr_db).connect() as con:
        emp = con.execute(
            text(
                "SELECT emp_id, display_name, role, department, status FROM employees"
                " WHERE emp_id = :e"
            ),
            {"e": emp_id},
        ).first()
        if emp is None:
            return None
        trainings = {
            str(r[0]): {"status": r[1], "completed_on": r[2], "expires_on": r[3]}
            for r in con.execute(
                text(
                    "SELECT course_id, status, completed_on, expires_on FROM training_records"
                    " WHERE emp_id = :e"
                ),
                {"e": emp_id},
            )
        }
        ack = con.execute(
            text(
                "SELECT policy_version, acknowledged_on FROM policy_acknowledgements"
                " WHERE emp_id = :e AND policy_id = 'WC-POL'"
                " ORDER BY acknowledged_on DESC, policy_version DESC LIMIT 1"
            ),
            {"e": emp_id},
        ).first()
    return {
        "emp_id": emp.emp_id,
        "name": emp.display_name,
        "role": emp.role,
        "department": emp.department,
        "active": emp.status == "active",
        "trainings": trainings,
        "policy_ack": {"version": ack[0], "acknowledged_on": ack[1]} if ack else None,
    }


def _rule_evidence(rule: str, employee: dict[str, Any] | None) -> dict[str, Any]:
    if employee is None:
        return {}
    if rule == "role":
        return {"role": employee["role"]}
    if rule == "policy_ack":
        return {"policy_ack": employee["policy_ack"]}
    found = employee["trainings"].get(rule)
    return {"training": found} if found else {"training": None}


@router.get("/cases/{case_id}/readiness")
def readiness(case_id: str, who: User, svc: Svc) -> dict[str, Any]:
    """Gate 1 as the Onboarding stage recorded it, with the HR records that evidence each rule.
    `decision` is null before the stage has run; nothing here re-evaluates a rule."""
    case = visible_case(svc, who, case_id)
    with transaction(svc.engine) as s:
        emp_id = reads.preparer_emp_id(s, case.tenant_id, case.id)
        runs = [r for r in reads.stage_runs(s, case.tenant_id, case.id) if r.stage == "onboarding"]
        facts = reads.list_for_case(s, case.tenant_id, case.id)
    latest = {f.key: f for f in facts if f.key.startswith("onb.rule.")}  # versions ascend
    employee = _employee(svc, emp_id) if emp_id else None
    run = runs[-1] if runs else None
    result = json.loads(run.result_json) if run and run.result_json else {}
    rules = [
        {
            "rule": key.removeprefix("onb.rule."),
            "outcome": f.value_text,
            "kind": "role"
            if key.endswith(".role")
            else "policy"
            if key.endswith(".policy_ack")
            else "training",
        }
        | _rule_evidence(key.removeprefix("onb.rule."), employee)
        for key, f in sorted(latest.items())
    ]
    public = None
    if employee is not None:
        public = {k: employee[k] for k in ("emp_id", "name", "role", "department", "active")}
    return {
        "case_id": case.id,
        "decision": run.decision if run else None,
        "checked_at": iso(run.ended_at or run.started_at) if run else None,
        "attempt": run.attempt if run else 0,
        "preparer": public,
        "rules": rules,
        "blockers": [
            {k: b.get(k) for k in ("code", "message", "next_action")}
            for b in result.get("blockers", [])
        ],
        "question": result.get("question"),
    }


# ---- history ------------------------------------------------------------------------------------
# Payload keys a case member may see, per event type. Hashes, input hashes, source refs, trace ids
# and model wording are never included; FACT_WRITTEN gives only the key, version and value, which
# the case views already show (the value is a ledger figure, never free text).
HISTORY_KEYS: dict[str, tuple[str, ...]] = {
    "CASE_CREATED": ("order_ref",),
    "FILE_UPLOADED": ("kind",),
    "PDF_DRAFTED": ("doc", "model", "drafted", "dropped"),
    "INJECTION_FLAGGED": ("kind", "flags"),
    "STAGE_COMPLETED": ("stage", "attempt", "decision"),
    "STATE_CHANGED": ("status", "current_stage"),
    "ROUTED": ("route", "status"),
    "DECISION_RECORDED": ("role", "decision", "return_stage", "comment"),
    "STAGE_RETRY_REQUESTED": ("stage",),
    "EXTRA_INVOCATION": ("stage", "name", "decision"),
    "GATE_OVERRIDE": ("stage",),
    "CRITIC_BLOCKED": ("stage", "codes"),
    "CRITIC_FALLBACK": ("stage",),
    "CRITIC_REROUTE": ("stage",),
    "LLM_FALLBACK": ("stage", "reason"),
    "GUARDRAIL_EVENT": ("rail", "rule_id", "action", "kinds", "count", "file_kind"),
    "TOOL_CALLED": ("agent", "tool"),
    "FACT_WRITTEN": ("key", "version", "value", "unit", "stage"),
    "STEP_UP_VERIFIED": (),
    "STEP_UP_FAILED": (),
    "CASE_DELETED": (),
}
# FACT_WRITTEN values are sent only for these units: figures, codes and flags. "json" and "text"
# facts (narratives, copilot answers, negotiation wording) keep their value in the audit log only.
FIGURE_UNITS = frozenset(
    {"INR", "enum", "bool", "rate", "codes", "rank", "week", "weeks", "offer_ids"}
)
MAX_TEXT = 500  # a comment longer than this is cut; the full text stays in the audit log


def _clip(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_TEXT:
        return value[:MAX_TEXT] + "…"
    return value


@router.get("/cases/{case_id}/history")
def history(case_id: str, who: User, svc: Svc) -> dict[str, Any]:
    """The case's events, oldest first, for any case member. Unknown event types are listed with
    no payload, so a new type never leaks a key before it is reviewed here."""
    case = visible_case(svc, who, case_id)
    with transaction(svc.engine) as s:
        events = reads.audit_events(s, case.tenant_id, case.id)
        broken = reads.verify_chain(s, who.tenant_id)
        ids = {e.actor for e in events}
        names = {
            u.id: (u.display_name or u.username, u.role)
            for u in s.scalars(
                select(UserRow).where(UserRow.tenant_id == case.tenant_id, UserRow.id.in_(ids))
            )
        }
    rows = []
    for e in events:
        payload = e.payload or {}
        allowed = HISTORY_KEYS.get(e.event_type, ())
        if e.event_type == "FACT_WRITTEN" and payload.get("unit") not in FIGURE_UNITS:
            allowed = tuple(k for k in allowed if k != "value")
        name, role = names.get(e.actor, (None, None))
        rows.append(
            {
                "seq": e.seq,
                "ts": e.ts,
                "event_type": e.event_type,
                "actor": e.actor,
                "actor_name": name,
                "actor_role": role,
                "details": {k: _clip(payload[k]) for k in allowed if k in payload},
            }
        )
    return {"case_id": case.id, "events": rows, "chain_ok": not broken}


# ---- Excel workbook import (ADR 0040) ------------------------------------------------------------
XLSX_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
    "application/zip",
}
LOCKED = frozenset({"AWAITING_APPROVAL", "HELD", "APPROVED", "REJECTED"})


@router.post("/cases/{case_id}/workbook", status_code=201)
async def import_workbook(
    request: Request,
    case_id: str,
    file: Annotated[UploadFile, File()],
    who: User,
    svc: Svc,
) -> dict[str, Any]:
    """The case template workbook → its JSON/CSV files, each validated and stored exactly as a
    single upload (UI-02). All or nothing: on any error nothing is stored and every error names
    the sheet, Excel row and column. Sheets left empty are skipped."""
    case = own_case(svc, who, case_id)
    if case.status in LOCKED:
        raise ProblemError(409, f"case is {case.status}; inputs are locked", ApiErrorCode.CONFLICT)
    if run_in_progress(svc.engine, case.id):
        raise ProblemError(409, "a run is in progress on this case", ApiErrorCode.RUN_IN_PROGRESS)
    limit = svc.settings.max_upload_bytes
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit + 64 * 1024:
        raise ProblemError(
            413, f"file is larger than {limit} bytes", ApiErrorCode.PAYLOAD_TOO_LARGE
        )
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if not (file.filename or "").lower().endswith(".xlsx") or content_type not in XLSX_TYPES:
        raise ProblemError(
            415, "upload an Excel .xlsx workbook", ApiErrorCode.UNSUPPORTED_MEDIA_TYPE
        )
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise ProblemError(
            413, f"file is larger than {limit} bytes", ApiErrorCode.PAYLOAD_TOO_LARGE
        )
    workbook.guard_zip(raw)
    try:
        files, errors = workbook.convert(io.BytesIO(raw), partial=True)
    except ProblemError:
        raise
    except Exception as exc:  # openpyxl raises many types on a damaged file
        raise ProblemError(
            422,
            "the workbook could not be read",
            errors=[{"field": None, "row": None, "reason": "the workbook is damaged or not .xlsx"}],
        ) from exc
    if errors:
        raise ProblemError(
            422,
            "workbook failed validation",
            errors=[
                {
                    "field": f"{e.tab}.{e.column}" if e.column else e.tab,
                    "row": e.row,
                    "reason": e.reason,
                }
                for e in errors[:100]
            ],
        )
    stored = []
    for name, body in files.items():
        kind = workbook.kind_of(name)
        result = store_upload(svc, case, who.user_id, kind, body.encode("utf-8"), body)
        stored.append({"name": name, **result})
    return {"case_id": case.id, "files": stored}


@router.get("/templates/case.xlsx", response_class=Response)
def case_template(
    who: User,
    svc: Svc,
    example: Annotated[bool, Query()] = False,
) -> Response:
    """The case workbook template. Default: blank (headers, types, dropdowns kept; the example rows
    removed). example=true: the committed file with the demo case filled in."""
    path = svc.settings.case_template
    if not path.is_file():
        raise ProblemError(404, "the case template is not installed", ApiErrorCode.NOT_FOUND)
    data = path.read_bytes()
    if not example:
        wb = load_workbook(io.BytesIO(data))
        for ws in wb.worksheets:
            if ws.title != "README" and ws.max_row >= workbook.DATA_ROW:
                ws.delete_rows(workbook.DATA_ROW, ws.max_row - workbook.DATA_ROW + 1)
        buf = io.BytesIO()
        wb.save(buf)
        data = buf.getvalue()
    name = "credassure-case-example.xlsx" if example else "credassure-case-template.xlsx"
    return Response(
        data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


# ---- ADR 0041: lender PDFs -> a draft the preparer reviews -----------------------------------
PDF_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}


def _open_inputs(svc: Svc, who: Any, case_id: str) -> Any:
    case = own_case(svc, who, case_id)
    if case.status in LOCKED:
        raise ProblemError(409, f"case is {case.status}; inputs are locked", ApiErrorCode.CONFLICT)
    if run_in_progress(svc.engine, case.id):
        raise ProblemError(409, "a run is in progress on this case", ApiErrorCode.RUN_IN_PROGRESS)
    return case


@router.post("/cases/{case_id}/pdf")
async def read_pdf(
    request: Request,
    case_id: str,
    doc: Annotated[pdf_intake.DocKind, Query()],
    file: Annotated[UploadFile, File()],
    who: User,
    svc: Svc,
) -> dict[str, Any]:
    """A text-layer PDF -> its text and, for an offer letter or schedule of charges, a draft the
    model quoted and code read (ADR 0041). Nothing is stored: the preparer reviews the draft and
    saves it through the ordinary upload path. Scanned PDFs are refused (no OCR, BRD §4.3)."""
    case = _open_inputs(svc, who, case_id)
    limit = svc.settings.max_upload_bytes
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit + 64 * 1024:
        raise ProblemError(
            413, f"file is larger than {limit} bytes", ApiErrorCode.PAYLOAD_TOO_LARGE
        )
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if not (file.filename or "").lower().endswith(".pdf") or content_type not in PDF_TYPES:
        raise ProblemError(415, "upload a .pdf file", ApiErrorCode.UNSUPPORTED_MEDIA_TYPE)
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise ProblemError(
            413, f"file is larger than {limit} bytes", ApiErrorCode.PAYLOAD_TOO_LARGE
        )
    text = pdf_intake.pdf_text(raw)
    llm = svc.llm if svc.settings.llm_enabled else None
    if doc == "offer":
        draft = pdf_intake.draft_offer(llm, text)
    elif doc == "schedule":
        draft = pdf_intake.draft_schedule(llm, text)
    else:
        draft = {"model": "not needed"}
    sha = hashlib.sha256(raw).hexdigest()
    # OBJ-08: the AI's part in data entry is on the record (counts only, never the text)
    svc.ledger.audit(
        case.id,
        "PDF_DRAFTED",
        {
            "doc": doc,
            "sha256": sha,
            "model": draft["model"],
            "drafted": len(draft.get("fields", {})) + len(draft.get("fees", draft.get("rows", []))),
            "dropped": draft.get("dropped", 0),
        },
    )
    return {"case_id": case.id, "doc": doc, "sha256": sha, "text": text, "draft": draft}


class ChargeRow(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    timing: Literal["upfront", "monthly", "annual"]
    amount: str = Field(min_length=1, max_length=200)


class KfsDocument(BaseModel):
    kfs_doc_id: str = Field(pattern=KFS_DOC_ID)
    offer_id: str = Field(pattern=OFFER_ID)
    version: int = Field(ge=1, le=99)
    which: Literal["kfs", "schedule"]
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(max_length=pdf_intake.MAX_CHARS)
    rows: list[ChargeRow] = Field(default_factory=list, max_length=40)


@router.post("/cases/{case_id}/kfs-document", status_code=201)
def save_kfs_document(case_id: str, body: KfsDocument, who: User, svc: Svc) -> dict[str, Any]:
    """A reviewed KFS or schedule of charges from a PDF, stored as the KFS document LendWise reads
    (ADR 0041). The rows the person confirmed become the charge table; the PDF text follows as
    data. Stored through the same validation, injection scan and audit as any upload."""
    case = _open_inputs(svc, who, case_id)
    if body.which == "schedule" and not body.rows:
        raise ProblemError(
            422,
            "a schedule of charges needs at least one charge",
            errors=[{"field": "rows", "row": None, "reason": "add the charges from the PDF"}],
        )
    doc_id = body.kfs_doc_id + ("-SCH" if body.which == "schedule" else "")
    markdown = pdf_intake.kfs_markdown(
        doc_id=doc_id,
        case_id=case.id,
        offer_id=body.offer_id,
        version=body.version,
        title=body.title,
        body=body.text,
        rows=[r.model_dump() for r in body.rows],
    )
    return store_upload(svc, case, who.user_id, "kfs", markdown.encode("utf-8"), markdown)
