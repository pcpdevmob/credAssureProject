"""PDF intake for lender documents (ADR 0041): text-layer PDF -> a draft the preparer reviews.

The model reads, code checks, a person confirms (the design principle, applied to data entry):
1. Code extracts the text layer with pypdf (no OCR: a scanned PDF is refused, BRD §4.3). Personal
   identifiers are redacted before the text goes anywhere (NFR-07).
2. For an offer letter or a schedule of charges, the model is asked only to *copy quotes* from the
   spotlighted text (BR-15). Code keeps a quote only if it appears in the text, and code - not the
   model - reads every amount, rate, date and term out of the quote with the VER-01 normaliser.
3. Nothing is stored here. The draft goes to a form; the preparer checks every field against the
   PDF and saves through the ordinary upload path, where the file is validated like any upload.
A KFS (free text) needs no model: its text becomes the KFS document body.
"""

import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from credassure.core.errors import LLMError
from credassure.core.ports import LLMPort
from credassure.core.prompts import registry as prompts
from credassure.core.structured import complete_model
from credassure.engines.normaliser import find_all
from credassure.gateway.problems import ProblemError
from credassure.security.pii import redact
from credassure.security.spotlight import spotlight

MAX_PAGES = 40
MAX_CHARS = 60_000  # extracted text kept for the draft and the KFS body
MODEL_CHARS = 12_000  # what the model sees (prompt budget, NFR-02); the rest is never drafted from
OFFER_PROMPT, SCHEDULE_PROMPT = "intake_offer_quotes", "intake_schedule_rows"
DocKind = Literal["offer", "kfs", "schedule"]


def _bad(reason: str) -> ProblemError:
    return ProblemError(
        422, "the PDF could not be read", errors=[{"field": None, "row": None, "reason": reason}]
    )


def pdf_text(raw: bytes) -> str:
    """The text layer of a PDF, identifiers redacted. Refuses encrypted, scanned or huge files."""
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    if not raw.startswith(b"%PDF-"):
        raise _bad("the file is not a PDF")
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
        if reader.is_encrypted:
            raise _bad("the PDF is password-protected; save an unprotected copy and try again")
        if len(reader.pages) > MAX_PAGES:
            raise _bad(f"the PDF has more than {MAX_PAGES} pages")
        parts: list[str] = []
        size = 0
        for page in reader.pages:
            text = page.extract_text() or ""
            parts.append(text)
            size += len(text)
            if size > MAX_CHARS:
                break
    except ProblemError:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError, OSError) as exc:
        raise _bad("the PDF is damaged or not readable") from exc
    text = "\n".join(parts)[:MAX_CHARS]
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(re.sub(r"\W", "", text)) < 20:
        raise _bad("no text found: the PDF looks scanned (an image). Scanned PDFs cannot be read")
    return redact(text)


def _norm(text: str) -> str:
    """Whitespace- and datamark-insensitive form for checking that a quote is in the text."""
    return re.sub(r"\s+", " ", text.replace("^", " ")).strip().lower()


def in_text(quote: str, text: str) -> bool:
    q = _norm(quote)
    return len(q) >= 2 and q in _norm(text)


# ---- offer letter ----------------------------------------------------------------------------
OfferField = Literal[
    "lender_name",
    "principal",
    "annual_rate",
    "rate_type",
    "benchmark",
    "spread",
    "tenure_months",
    "moratorium_months",
    "repayment_method",
    "stated_instalment",
    "issue_date",
    "disbursal_date",
    "first_repayment_date",
    "insurance_premium",
    "guarantee_fee",
    "prepayment_terms",
]


class FieldQuote(BaseModel):
    field: OfferField
    quote: str = Field(max_length=300)


class FeeQuote(BaseModel):
    name: str = Field(max_length=120)
    timing: Literal["upfront", "monthly", "annual"]
    amount: str = Field(max_length=200)


class OfferQuotes(BaseModel):
    fields: list[FieldQuote] = Field(default_factory=list, max_length=40)
    fees: list[FeeQuote] = Field(default_factory=list, max_length=20)


class ScheduleQuotes(BaseModel):
    rows: list[FeeQuote] = Field(default_factory=list, max_length=30)


@dataclass(frozen=True)
class Drafted:
    value: Any
    quote: str


KIND = {
    "principal": "money",
    "stated_instalment": "money",
    "insurance_premium": "money",
    "annual_rate": "rate",
    "spread": "rate",
    "guarantee_fee": "rate",
    "tenure_months": "number",
    "moratorium_months": "number",
    "issue_date": "date",
    "disbursal_date": "date",
    "first_repayment_date": "date",
}
LENDER_NAME = re.compile(r"^[A-Za-z][A-Za-z .,&()'-]{0,119}$")


def read_field(field: str, quote: str) -> Any | None:
    """The value code reads from one quote, or None when the quote does not hold exactly one."""
    if field in KIND:
        want = KIND[field]
        hits = [h for h in find_all(quote) if h.kind == want]
        if want == "number" and not hits:  # "12 months": the normaliser may read a bare number
            hits = [h for h in find_all(quote) if h.kind == "number"]
        if len(hits) != 1:
            return None
        value = hits[0].value
        if want == "number":
            n = Decimal(str(value))
            return int(n) if n == n.to_integral_value() and 0 <= n <= 600 else None
        return value.isoformat() if isinstance(value, date) else str(value)
    low = quote.lower()
    if field == "rate_type":
        found = {"floating"} if re.search(r"floating|variable|linked to", low) else set()
        found |= {"fixed"} if re.search(r"\bfixed\b", low) else set()
        return found.pop() if len(found) == 1 else None
    if field == "benchmark":
        found = {b for b in ("EBLR", "MCLR") if b.lower() in low}
        if re.search(r"repo[- ]linked|rllr|external benchmark", low):
            found.add("EBLR")
        return found.pop() if len(found) == 1 else None
    if field == "repayment_method":
        if re.search(r"\bemi\b|equated", low):
            return "emi"
        return "equal_principal" if re.search(r"equal principal|principal in equal", low) else None
    if field == "lender_name":
        name = quote.strip().strip(".,")
        return name if LENDER_NAME.match(name) else None
    if field == "prepayment_terms":
        return quote.strip()[:300] or None
    return None


def fee_from(amount: str) -> dict[str, Any] | None:
    """A fee's basis and value read by code from its amount text (as engines.offer_audit reads a
    schedule row): "2.35% of the loan amount + GST" or "₹25,000 + GST"."""
    hits = find_all(amount)
    if len(hits) != 1:
        return None
    hit, low = hits[0], amount.lower()
    gst = not re.search(r"gst[ -]exempt|exempt from gst|no gst|without gst|gst nil", low)
    if hit.kind == "rate" and re.search(r"of the (loan|principal|sanctioned)", low):
        return {"basis": "pct_of_principal", "value": str(hit.value), "gst_applicable": gst}
    if hit.kind == "money":
        return {"basis": "fixed", "value": str(hit.value), "gst_applicable": gst}
    return None


def _ask(llm: LLMPort | None, name: str, schema: type[BaseModel], text: str) -> Any | None:
    if llm is None:
        return None
    spot = spotlight([("pdf", text[:MODEL_CHARS])])
    prompt = prompts()[name].render(preamble=spot.preamble, document=spot.text)
    try:
        return complete_model(llm, name, schema, prompt)
    except LLMError:
        return None


def draft_offer(llm: LLMPort | None, text: str) -> dict[str, Any]:
    """Offer fields and fees with the quote each came from. Fields the model did not quote, or
    whose quote is not in the PDF or does not read as one value, are left for the person."""
    got = _ask(llm, OFFER_PROMPT, OfferQuotes, text)
    fields: dict[str, dict[str, Any]] = {}
    fees: list[dict[str, Any]] = []
    dropped = 0
    if isinstance(got, OfferQuotes):
        for fq in got.fields:
            value = read_field(fq.field, fq.quote) if in_text(fq.quote, text) else None
            if value is None or fq.field in fields:
                dropped += 1
                continue
            fields[fq.field] = {"value": value, "quote": fq.quote.replace("^", " ")}
        for fee in got.fees:
            priced = fee_from(fee.amount) if in_text(fee.amount, text) else None
            if priced is None or not in_text(fee.name, text):
                dropped += 1
                continue
            fees.append(
                {
                    "name": fee.name.replace("^", " ").strip(),
                    "timing": fee.timing,
                    **priced,
                    "quote": fee.amount.replace("^", " "),
                }
            )
    return {
        "model": "off" if llm is None else "used" if got is not None else "unavailable",
        "fields": fields,
        "fees": fees,
        "dropped": dropped,
    }


def draft_schedule(llm: LLMPort | None, text: str) -> dict[str, Any]:
    """Charge rows (name, timing, amount text) the model copied and code found in the PDF."""
    got = _ask(llm, SCHEDULE_PROMPT, ScheduleQuotes, text)
    rows, dropped = [], 0
    if isinstance(got, ScheduleQuotes):
        for r in got.rows:
            if in_text(r.name, text) and in_text(r.amount, text):
                rows.append(
                    {
                        "name": r.name.replace("^", " ").strip(),
                        "timing": r.timing,
                        "amount": r.amount.replace("^", " ").strip(),
                    }
                )
            else:
                dropped += 1
    return {
        "model": "off" if llm is None else "used" if got is not None else "unavailable",
        "rows": rows,
        "dropped": dropped,
    }


# ---- KFS documents ---------------------------------------------------------------------------
CELL = re.compile(r"[|\n\r]")


def kfs_markdown(
    *,
    doc_id: str,
    case_id: str,
    offer_id: str,
    version: int,
    title: str,
    body: str,
    rows: list[dict[str, str]] | None = None,
) -> str:
    """A KFS or schedule-of-charges document in the format the upload accepts (frontmatter + body).
    Reviewed rows become the canonical table LendWise reads (`| name | timing | amount |`); the PDF
    text follows as data. Pipes in the PDF text are neutralised so text can never become a row."""
    lines = [
        "---",
        f"doc_id: {doc_id}",
        "collection: kfs",
        f"case_id: {case_id}",
        f"offer_id: {offer_id}",
        f"offer_version: {version}",
        "source: pdf",
        "schema_version: 1.0",
        "---",
        f"# {CELL.sub(' ', title)[:200]}",
        "",
    ]
    if rows:
        lines += ["| Charge | Timing | Amount |", "|---|---|---|"]
        lines += [
            f"| {CELL.sub(' ', r['name']).strip()} | {r['timing']} | "
            f"{CELL.sub(' ', r['amount']).strip()} |"
            for r in rows
        ]
        lines.append("")
    lines += ["## Text of the PDF", "", body.replace("|", "/")]
    return "\n".join(lines) + "\n"
