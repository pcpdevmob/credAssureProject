"""Tracing spans and the test capture hook (scope #19 plan span, OBJ-08 traceability)."""

from credassure.observability.tracing import capture, span


def test_OBJ08_capture_collects_span_names_and_attrs() -> None:
    with capture() as spans, span("plan", case_id="CA-2026-0001", accepted=True):
        pass
    assert spans == [{"name": "plan", "case_id": "CA-2026-0001", "accepted": True}]


def test_OBJ08_nested_spans_are_all_captured_outer_first() -> None:
    with capture() as spans:
        with span("stage", stage="lendwise"), span("tool", tool="price_offer"):
            pass
        with span("stage", stage="critic"):
            pass
    assert [s["name"] for s in spans] == ["stage", "tool", "stage"]
    assert spans[1]["tool"] == "price_offer"
    assert spans[2]["stage"] == "critic"


def test_OBJ08_spans_outside_capture_are_not_collected() -> None:
    with span("before"):
        pass
    with capture() as spans, span("inside"):
        pass
    with span("after"):
        pass
    assert [s["name"] for s in spans] == ["inside"]
