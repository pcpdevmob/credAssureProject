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


def test_E11_S3_exporter_runs_on_exit_with_duration_and_error() -> None:
    import pytest

    from credassure.observability.tracing import set_exporter

    seen: list[tuple[str, dict[str, object]]] = []
    set_exporter(lambda name, attrs: seen.append((name, attrs)))
    try:
        with span("ok", tool="t"):
            assert seen == []  # nothing exported until the span ends
        with pytest.raises(KeyError), span("boom"):
            raise KeyError("x")
    finally:
        set_exporter(None)
    (ok_name, ok), (boom_name, boom) = seen
    assert ok_name == "ok" and ok["tool"] == "t"
    assert isinstance(ok["duration_ms"], float) and ok["error"] is None
    assert boom_name == "boom" and boom["error"] == "KeyError"


def test_E11_nested_span_inherits_the_trace_id() -> None:
    with capture() as spans, span("stage", trace_id="t" * 32), span("tool", tool="x"):
        pass
    assert spans[1]["trace_id"] == "t" * 32
