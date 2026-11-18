"""A live run outlasts the 30-minute access token: the harness signs in again (2026-11-18 e2e 401s)."""

from typing import Any

import pytest

from credassure.evaluation import harness


class _Resp:
    def __init__(self, n: int) -> None:
        self.n = n

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"access_token": f"t{self.n}"}


class _Client:
    def __init__(self) -> None:
        self.logins = 0

    def post(self, path: str, json: Any) -> _Resp:
        assert path == "/v1/auth/token"
        self.logins += 1
        return _Resp(self.logins)


def test_harness_reuses_a_token_then_signs_in_again(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [1000.0]
    monkeypatch.setattr(harness.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(harness, "known_doc_ids", lambda: set())
    c = _Client()
    h = harness.Harness(c, "pw", route_fn=lambda a, r: "x")  # type: ignore[arg-type]
    assert h.h("demo.preparer") == {"Authorization": "Bearer t1"}
    clock[0] += harness.TOKEN_REUSE_S - 1
    assert h.h("demo.preparer")["Authorization"] == "Bearer t1" and c.logins == 1
    clock[0] += 2
    assert h.h("demo.preparer")["Authorization"] == "Bearer t2" and c.logins == 2
    assert harness.TOKEN_REUSE_S < 30 * 60
