"""Phase 8b tracing exporter (NFR-07 PII masking, NFR-09 tracing, OBJ-08; phase8-api-spec.md).

No Langfuse, no network: the client is a recording fake.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest

from credassure.observability import tracing as obs

PAN, EMAIL = "ABCDE1234F", "preparer@example.com"


class _Obs:
    def __init__(self) -> None:
        self.ended = 0

    def end(self) -> None:
        self.ended += 1


class FakeClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.started: list[dict[str, Any]] = []
        self.obs = _Obs()

    def start_observation(self, **kwargs: Any) -> _Obs:
        if self.fail:
            raise RuntimeError("langfuse down")
        self.started.append(kwargs)
        return self.obs


def _settings(**overrides: Any) -> Any:
    from credassure.gateway.settings import Settings

    return Settings(_env_file=None, app_env="test", jwt_secret="x" * 40, **overrides)  # type: ignore[call-arg]


@pytest.fixture(autouse=True)
def _no_exporter() -> Iterator[None]:
    yield
    obs.set_exporter(None)


def test_NFR07_mask_redacts_nested_pii_and_keeps_non_strings() -> None:
    from credassure.gateway.tracing import mask

    data = {
        "who": {"pan": f"PAN {PAN}", "list": [EMAIL, (f"x {PAN}", 7)]},
        PAN: 1,
        "n": 3,
        "ok": None,
    }
    masked = mask(data)
    text = repr(masked)
    assert PAN not in text and EMAIL not in text
    assert masked["n"] == 3 and masked["ok"] is None
    assert data["who"]["pan"] == f"PAN {PAN}"  # input untouched (copy)


def test_NFR09_exporter_starts_and_ends_a_masked_span() -> None:
    from credassure.gateway.tracing import make_exporter

    client = FakeClient()
    make_exporter(client)("plan", {"case_id": "CA-2026-0001", "note": EMAIL})
    assert len(client.started) == 1
    call = client.started[0]
    assert call["name"] == "plan"
    assert call["as_type"] == "span"
    assert call["metadata"]["case_id"] == "CA-2026-0001"
    assert EMAIL not in repr(call["metadata"])
    assert client.obs.ended == 1


def test_NFR09_exporter_swallows_client_errors() -> None:
    from credassure.gateway.tracing import make_exporter

    make_exporter(FakeClient(fail=True))("plan", {"case_id": "CA-2026-0001"})  # must not raise


def _recording() -> tuple[list[str], Callable[[str, dict[str, Any]], None]]:
    seen: list[str] = []
    return seen, lambda name, attrs: seen.append(name)


@pytest.mark.parametrize(
    "overrides",
    [
        {"tracing_enabled": False, "langfuse_public_key": "pk", "langfuse_secret_key": "sk"},
        {"tracing_enabled": True},
        {"tracing_enabled": True, "langfuse_public_key": "pk"},
    ],
)
def test_NFR09_configure_off_or_missing_keys_installs_nothing(overrides: dict[str, Any]) -> None:
    from credassure.gateway.tracing import configure

    factory_calls: list[dict[str, Any]] = []
    seen, recorder = _recording()
    obs.set_exporter(recorder)  # a previous exporter must be uninstalled
    assert configure(_settings(**overrides), lambda **kw: factory_calls.append(kw)) is False
    with obs.span("probe"):
        pass
    assert seen == []
    assert factory_calls == []


def test_NFR09_configure_with_keys_installs_masked_exporter() -> None:
    from credassure.gateway.tracing import configure

    client = FakeClient()
    factory_calls: list[dict[str, Any]] = []

    def factory(**kwargs: Any) -> FakeClient:
        factory_calls.append(kwargs)
        return client

    settings = _settings(tracing_enabled=True, langfuse_public_key="pk", langfuse_secret_key="sk")
    assert configure(settings, factory) is True
    assert len(factory_calls) == 1
    assert {"public_key", "secret_key", "host", "mask"} <= factory_calls[0].keys()
    assert callable(factory_calls[0]["mask"])
    with obs.span("probe", note=PAN):
        pass
    assert [c["name"] for c in client.started] == ["probe"]
    assert PAN not in repr(client.started[0]["metadata"])


def test_NFR09_app_with_tracing_off_serves_live(make_client: Callable[..., Any]) -> None:
    r = make_client(llm_enabled=False).get("/v1/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_NFR09_exporter_joins_every_span_to_the_run_trace() -> None:
    """BRD §14: spans carrying the run's trace_id are exported into that one Langfuse trace."""
    from credassure.gateway.tracing import make_exporter

    client = FakeClient()
    export = make_exporter(client)
    export("plan", {"trace_id": "a" * 32, "case_id": "CA-2026-0001"})
    export("stage", {"trace_id": "a" * 32, "stage": "onboarding"})
    export("orphan", {"case_id": "CA-2026-0001"})
    contexts = [c["trace_context"] for c in client.started]
    assert contexts == [{"trace_id": "a" * 32}, {"trace_id": "a" * 32}, None]
