"""safety_v2 against a live gateway (K5, 25 Nov). The first Mac run scored the gateway's rate limiter
(429) and read case outcomes before the background run had finished; these tests pin both fixes."""

from typing import Any

import pytest

from credassure.evaluation import safety_v2 as sv


class Resp:
    def __init__(self, status: int, body: Any = None, headers: dict[str, str] | None = None):
        self.status_code, self._body, self.headers = status, body or {}, headers or {}

    def json(self) -> Any:
        return self._body


class Scripted:
    """Answers each call from a queue per method and records what was asked."""

    def __init__(self, get: list[Resp] | None = None, post: list[Resp] | None = None):
        self.queues = {"get": list(get or []), "post": list(post or [])}
        self.calls: list[tuple[str, str]] = []

    def get(self, url: str, **_: Any) -> Resp:
        self.calls.append(("get", url))
        return self.queues["get"].pop(0)

    def post(self, url: str, **_: Any) -> Resp:
        self.calls.append(("post", url))
        return self.queues["post"].pop(0)


def test_paced_client_waits_out_429_and_sends_the_same_request_again() -> None:
    inner = Scripted(
        post=[Resp(429, headers={"Retry-After": "7"}), Resp(429), Resp(200, {"ok": 1})]
    )
    slept: list[float] = []
    client = sv.PacedClient(inner, wait=15.0, sleep=slept.append)
    r = client.post("/v1/cases/CA-1/chat", json={"message": "hi"})
    assert r.status_code == 200
    assert inner.calls == [("post", "/v1/cases/CA-1/chat")] * 3
    assert slept == [7.0, 15.0]


def test_paced_client_gives_up_after_its_tries_and_returns_the_429() -> None:
    inner = Scripted(get=[Resp(429)] * 3)
    client = sv.PacedClient(inner, tries=3, sleep=lambda _: None)
    assert client.get("/v1/cases/CA-1").status_code == 429


def test_paced_client_passes_other_statuses_through_untouched() -> None:
    inner = Scripted(post=[Resp(403)])
    client = sv.PacedClient(inner, sleep=lambda _: pytest.fail("no wait on a 403"))
    assert client.post("/v1/cases/CA-1/decision").status_code == 403


def _runner(client: Any) -> sv.Runner:
    r = sv.Runner(client, "pw", sleep=lambda _: None)
    r._headers["preparer"] = {"Authorization": "Bearer t"}
    return r


def test_wait_for_job_polls_until_the_run_has_ended() -> None:
    jobs = [Resp(200, {"status": s}) for s in ("queued", "running", "running", "succeeded")]
    client = Scripted(get=jobs)
    _runner(client).wait_for_job("/v1/jobs/J1")
    assert client.calls == [("get", "/v1/jobs/J1")] * 4


@pytest.mark.parametrize("end", ["failed", "abandoned"])
def test_wait_for_job_returns_on_any_end_state(end: str) -> None:
    client = Scripted(get=[Resp(200, {"status": end})])
    _runner(client).wait_for_job("/v1/jobs/J1")
    assert len(client.calls) == 1


def test_wait_for_job_fails_the_item_when_the_run_never_ends() -> None:
    client = Scripted(get=[Resp(200, {"status": "running"})] * 5)
    runner = _runner(client)
    runner.run_timeout, runner.poll_seconds = 6.0, 2.0
    with pytest.raises(RuntimeError, match="still running"):
        runner.wait_for_job("/v1/jobs/J1")


def test_wait_for_job_fails_on_an_unreadable_job() -> None:
    client = Scripted(get=[Resp(404)])
    with pytest.raises(RuntimeError, match="job status 404"):
        _runner(client).wait_for_job("/v1/jobs/J1")
