"""Plan v3.4 P3 (ADR 0029, 0030): rail events in the audit log, the trace-leak test (scope #59),
gen_ai.* export attributes (R5) and data classes."""

from collections.abc import Callable
from typing import Any

from credassure.guardrails import data_classes, pii, recognisers
from credassure.ledger import reads, session
from credassure.observability.tracing import capture, set_exporter

NEW_CASE = {
    "msme_name": "Demo Electronics Pvt Ltd",
    "order_ref": "PO-P3",
    "order_value_paise": 3_20_00_000_00,
    "indicative_amount_paise": 2_00_00_000_00,
    "due_date": "2027-05-15",
}
_BODY = "52341287650"
PLANTED = {  # one synthetic value per identifier type the redactor knows
    "AADHAAR": _BODY + pii.verhoeff_digit(_BODY),
    "PAN": "ABCDE1234F",
    "IFSC": "HDFC0001234",
    "PHONE": "9876501234",
    "EMAIL": "ravi.k@example.com",
    "ACCOUNT": "account no 123456789012",
    "GSTIN": "27AAPFU0939F1Z" + recognisers.gstin_check_char("27AAPFU0939F1Z"),
    "UPI": "ravi.k@okaxis",
    "CARD": "4111 1111 1111 1111",
    "UDYAM": "UDYAM-MH-26-0012345",
}


class _Obs:
    def end(self) -> None:
        pass


class _Client:
    def __init__(self) -> None:
        self.started: list[dict[str, Any]] = []

    def start_observation(self, **kw: Any) -> _Obs:
        self.started.append(kw)
        return _Obs()


def _secrets(value: str) -> list[str]:
    """The part of a planted value that must never appear (the account keyword may)."""
    return [value.split()[-1]] if value.startswith("account") else [value, value.replace(" ", "")]


def test_scope59_planted_identifiers_never_reach_traces_exports_or_audit(
    client: Any, login: Callable[..., dict[str, str]]
) -> None:
    from credassure.gateway.tracing import make_exporter

    h = login(client, "prep.e001")
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    message = "Details: " + "; ".join(PLANTED.values()) + ". Am I cleared?"
    sink = _Client()
    set_exporter(make_exporter(sink))
    try:
        with capture() as spans:
            r = client.post(f"/v1/cases/{case_id}/chat", json={"message": message}, headers=h)
    finally:
        set_exporter(None)
    assert r.status_code == 200, r.text
    with session.transaction(session.case_engine(client.db)) as s:
        audit = [(e.event_type, e.payload) for e in reads.audit_events(s, "default", case_id)]
        user = reads.user_by_name(s, "prep.e001")
        assert user is not None
        stored = [t.redacted_text for t in reads.chat_history(s, "default", case_id, user.id, 10)]
    haystack = str(spans) + str(sink.started) + str(audit) + str(stored) + r.text
    hits = [kind for kind, value in PLANTED.items() if any(v in haystack for v in _secrets(value))]
    assert hits == []  # 0 hits across traces, exported spans, audit and stored chat
    events = [p for t, p in audit if t == "GUARDRAIL_EVENT"]
    assert [(e["rail"], e["rule_id"], e["action"]) for e in events] == [
        ("R1", "R1.chat_pii_redacted", "redact")
    ]
    assert set(events[0]["kinds"]) == set(PLANTED)


def test_scope56_refused_upload_is_an_audited_guardrail_block(
    client: Any, login: Callable[..., dict[str, str]]
) -> None:
    h = login(client, "prep.e001")
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    body = b"invoice_id,customer,amount,due_week,expected_week\nINV-1,ABCDE1234F,100,3,4\n"
    r = client.post(
        f"/v1/cases/{case_id}/files",
        params={"kind": "receivables"},
        files={"file": ("receivables.csv", body, "text/csv")},
        headers=h,
    )
    assert r.status_code == 422
    with session.transaction(session.case_engine(client.db)) as s:
        events = [
            e.payload
            for e in reads.audit_events(s, "default", case_id)
            if e.event_type == "GUARDRAIL_EVENT"
        ]
    assert [(e["rule_id"], e["action"], e["kinds"]) for e in events] == [
        ("R1.upload_pii_refused", "block", ["PAN"])
    ]
    assert "ABCDE1234F" not in str(events)


def test_R5_llm_spans_export_gen_ai_attributes_masked() -> None:
    from credassure.gateway.tracing import make_exporter

    sink = _Client()
    make_exporter(sink, "qwen3:8b")(
        "llm",
        {
            "prompt": "wc_explain",
            "prompt_version": "2.0.0",
            "prompt_tokens": 120,
            "input": f"PAN {PLANTED['PAN']}",
        },
    )
    (call,) = sink.started
    meta = call["metadata"]
    assert call["as_type"] == "generation"
    assert meta["gen_ai.operation.name"] == "chat" and meta["gen_ai.request.model"] == "qwen3:8b"
    assert (
        meta["gen_ai.usage.input_tokens"] == 120 and meta["credassure.prompt.name"] == "wc_explain"
    )
    assert PLANTED["PAN"] not in str(meta)


def test_scope59_every_pii_kind_has_a_data_class_and_c4_never_reaches_a_span() -> None:
    kinds = {h.kind for h in pii.find("; ".join(PLANTED.values()))}
    assert kinds == set(PLANTED)
    assert {data_classes.of_pii(k) for k in kinds} <= {
        data_classes.DataClass.C3,
        data_classes.DataClass.C4,
    }
    assert data_classes.of_pii("SOMETHING_NEW") is data_classes.DataClass.C4  # fail closed
    assert data_classes.of_collection("public") is data_classes.DataClass.C1
