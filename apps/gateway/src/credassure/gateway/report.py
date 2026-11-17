"""Proposal report: rendering, versioning and staleness (UI-08, VER-04, scope #6, #10, #33).

A report version is the ledger fact `report`: the {key: version} of every stage fact it was
rendered from. The ledger already gives it append-only versions, audit and lineage. A version is
**stale** when a stage fact has a newer version (or a new key) than it pinned, or a case file of a
kind the pinned facts read was uploaded after them with bytes they never read. Any version renders
exactly as it was, from its pinned fact versions. Figures carry their ledger key and version so
the UI can open the provenance drawer; positions are offsets into the section's plain text.
"""

import json
import re
from decimal import Decimal
from typing import Any

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from credassure.core.money import format_inr, from_paise, to_paise
from credassure.ledger import reads
from credassure.ledger.models import Case, CaseFile, LedgerFact
from credassure.ledger.session import transaction
from credassure.reports.sections import required_sections

REPORT_KEY = "report"
PRODUCER = "reports@1"
STAGE_PREFIXES = {
    "onb.": "onboarding",
    "wc.": "working_capital",
    "lw.": "lendwise",
    "ver.": "critic",
}
INTERNAL_APPROVAL = (
    "Approval in CredAssure is an internal sign-off on this proposal only. It is not loan "
    "acceptance: the MSME chooses its lender outside the system (APR-06, BR-13)."
)
_OFFER = re.compile(r"^lw\.(OF-[A-Za-z0-9-]+)\.v(\d+)\.")


def _stage(key: str) -> str | None:
    return next((st for p, st in STAGE_PREFIXES.items() if key.startswith(p)), None)


def _current(facts: list[LedgerFact]) -> dict[str, LedgerFact]:
    latest: dict[str, LedgerFact] = {}
    for f in facts:  # versions ascend per key
        if _stage(f.key):
            latest[f.key] = f
    return latest


def superseded_uploads(fact: LedgerFact, files: list[CaseFile]) -> set[str]:
    """Kinds of case files uploaded after `fact` whose bytes it never read (sha differs)."""
    tokens = [t.strip().removeprefix("case_files:") for t in fact.source_ref.split(",")]
    read = [t.rpartition("@") for t in tokens if "@" in t]
    kinds = {label.partition(":")[0] for label, _, sha in read if len(sha) >= 12}
    shas = {sha for _, _, sha in read}
    return {
        f.kind
        for f in files
        if f.kind in kinds and f.created_at > fact.created_at and f.sha256[:12] not in shas
    }


def state(s: Session, case: Case) -> dict[str, Any]:
    """Version and staleness of the case's latest report."""
    facts = reads.list_for_case(s, case.tenant_id, case.id)
    current = _current(facts)
    rep = next((f for f in reversed(facts) if f.key == REPORT_KEY), None)
    if rep is None:
        pinned = {k: f.version for k, f in current.items()}
        return {"version": None, "stale": True, "reasons": ["no_version"], "pinned": pinned}
    pinned = json.loads(rep.value_text)["pinned"]
    reasons = {str(_stage(k)) for k, f in current.items() if pinned.get(k) != f.version}
    by_version = {(f.key, f.version): f for f in facts}
    files = reads.case_files(s, case.tenant_id, case.id)
    for key, version in pinned.items():
        if (fact := by_version.get((key, version))) is not None:
            reasons |= {f"upload:{kind}" for kind in superseded_uploads(fact, files)}
    return {
        "version": rep.version,
        "stale": bool(reasons),
        "reasons": sorted(reasons),
        "pinned": pinned,
    }


def snapshot(engine: Engine, case: Case, put_fact: Any) -> None:
    """Pin the current stage facts as a new report version (no-op when nothing changed, because
    the ledger skips an identical rewrite). Read first, then write: one writer at a time."""
    with transaction(engine) as s:
        facts = reads.list_for_case(s, case.tenant_id, case.id)
    pinned = {k: f.version for k, f in _current(facts).items()}
    put_fact(
        case.id,
        REPORT_KEY,
        json.dumps({"pinned": pinned}, sort_keys=True),
        unit="json",
        source_type="ledger_fact",
        source_ref=",".join(sorted(pinned)),
        produced_by=PRODUCER,
    )


class _Section:
    def __init__(self, title: str, values: dict[str, LedgerFact]) -> None:
        self.title, self.values, self.text = title, values, ""
        self.figures: list[dict[str, Any]] = []

    def put(self, text: str) -> "_Section":
        self.text += text
        return self

    def fig(self, key: str, display: str | None = None) -> "_Section":
        fact = self.values.get(key)
        if fact is None:
            return self.put("—")
        shown = display or _display(fact)
        self.figures.append(
            {
                "key": key,
                "version": fact.version,
                "start": len(self.text),
                "end": len(self.text) + len(shown),
                "display": shown,
            }
        )
        return self.put(shown)

    def narrative(self, key: str) -> "_Section":
        """Model or template text whose figures were rendered by code from `slots` (9d)."""
        fact = self.values.get(key)
        if fact is None:
            return self
        data = json.loads(fact.value_text)
        text = str(data.get("text", ""))
        if not text:
            return self
        if self.text:
            self.put("\n\n")
        base, taken = len(self.text), set()
        for slot, shown in (data.get("slots") or {}).items():
            if slot not in self.values or not shown or not re.search(r"\d", str(shown)):
                continue  # only ledger figures (cmp.* and wording slots have no lineage)
            for m in re.finditer(re.escape(str(shown)), text):
                if m.start() not in taken:
                    taken.add(m.start())
                    self.figures.append(
                        {
                            "key": slot,
                            "version": self.values[slot].version,
                            "start": base + m.start(),
                            "end": base + m.end(),
                            "display": str(shown),
                        }
                    )
        self.figures.sort(key=lambda f: f["start"])
        return self.put(text)

    def view(self) -> dict[str, Any]:
        return {"title": self.title, "text": self.text, "figures": self.figures}


def _display(fact: LedgerFact) -> str:
    if fact.unit == "INR":
        return format_inr(from_paise(to_paise(Decimal(fact.value_text))))
    if fact.unit == "rate":
        return f"{(Decimal(fact.value_text) * 100).quantize(Decimal('0.01'))}%"
    return fact.value_text


def render(s: Session, case: Case, version: int | None = None) -> dict[str, Any] | None:
    """The report at `version` (latest when None; a draft from current facts when none exists).
    None when the asked version does not exist."""
    latest = state(s, case)
    pinned = latest["pinned"]
    shown_version = latest["version"]
    if version is not None:
        rep = reads.get_fact(s, case.tenant_id, case.id, REPORT_KEY, version)
        if rep is None:
            return None
        pinned, shown_version = json.loads(rep.value_text)["pinned"], version
    stale = latest["stale"] or shown_version != latest["version"]
    by_version = {(f.key, f.version): f for f in reads.list_for_case(s, case.tenant_id, case.id)}
    values = {k: by_version[(k, v)] for k, v in pinned.items() if (k, v) in by_version}
    sections = _sections(s, case, values)
    return {
        "case_id": case.id,
        "version": shown_version,
        "latest_version": latest["version"],
        "stale": stale,
        "reasons": latest["reasons"] if shown_version == latest["version"] else ["newer_version"],
        "pinned": pinned,
        "sections": [sec.view() for sec in sections],
    }


def _sections(s: Session, case: Case, values: dict[str, LedgerFact]) -> list[_Section]:
    def sec(title: str) -> _Section:
        return _Section(title, values)

    def value(key: str, default: str = "—") -> str:
        return values[key].value_text if key in values else default

    summary = sec("Case summary").put(f"{case.msme_name} · order {case.order_ref} · ")
    summary.put(
        f"order value {format_inr(from_paise(case.order_value_paise))} · indicative request "
    )
    summary.put(f"{format_inr(from_paise(case.indicative_amount_paise))}. Validated need: ")
    summary.fig("wc.recommended_amount").put(f". Status {case.status}.")

    ready = sec("Preparer readiness").put(f"Gate: {value('onb.gate')}.").narrative("onb.narrative")

    funding = sec("Funding need").put(f"Gate: {value('wc.gate')}. Peak shortfall ")
    funding.fig("wc.peak_shortfall").put(" in week ").fig("wc.peak_week").put("; recommended ")
    funding.fig("wc.recommended_amount").put(".").narrative("wc.narrative")

    offers = sec("Offer comparison").put(
        f"Gate: {value('lw.gate')}. Ranking: {value('lw.ranking', 'none')}."
    )
    latest: dict[str, int] = {}
    for key in values:
        if m := _OFFER.match(key):
            latest[m[1]] = max(latest.get(m[1], 0), int(m[2]))
    for oid, ver in sorted(latest.items()):
        p = f"lw.{oid}.v{ver}."
        offers.put(f"\n- {oid} v{ver}: APR ").fig(p + "apr").put(", total cost ").fig(
            p + "total_cost"
        )
        offers.put(", amount received ").fig(p + "amount_received")
        offers.put(
            f", rank {value(p + 'rank', 'unranked')}, affordable {value(p + 'affordable', '—')}"
        )
        offers.put(f", flags {value(p + 'flags', 'none')}.")
    offers.narrative("lw.narrative")

    nego = sec("Negotiation")
    nego.put(f"Fee-waiver round: {value('lw.negotiation.status', 'not sent')}.")

    findings = json.loads(value("ver.findings", "[]"))
    verify = sec("Verification").put(
        "Verification Critic: no critical finding."
        if not findings
        else f"Verification Critic findings: {len(findings)}."
    )

    routing = sec("Approval routing").put(f"Route: {case.route or 'not routed yet'}.")
    decisions = reads.approvals(s, case.tenant_id, case.id)
    history = sec("Decision history").put(
        "\n".join(f"- {a.created_at.isoformat()} {a.role}: {a.decision}" for a in decisions)
        or "No decision yet."
    )
    runs = reads.stage_runs(s, case.tenant_id, case.id)
    traces = sec("Trace IDs").put(
        "\n".join(f"- {r.stage} attempt {r.attempt}: {r.trace_id}" for r in runs) or "No run yet."
    )
    internal = sec("Approval is internal, not loan acceptance").put(INTERNAL_APPROVAL)
    out = [summary, ready, funding, offers, nego, verify, routing, history, traces, internal]
    if [x.title for x in out] != list(required_sections()):  # VER-04: fail closed
        raise RuntimeError("report sections do not match sections.yaml")
    return out


_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()<>#!|])")


def markdown(report: dict[str, Any]) -> str:
    """S6: report text is literal Markdown (no links, images or HTML)."""
    head = f"# Proposal {report['case_id']} — report version {report['version'] or 'draft'}"
    note = (
        "**Stale:** the figures changed after this version; create a new version."
        if report["stale"]
        else "Current version."
    )
    body = [
        f"## {sec['title']}\n\n{_MD_SPECIAL.sub(r'\\\1', sec['text'])}"
        for sec in report["sections"]
    ]
    return "\n\n".join([head, note, *body]) + "\n"
