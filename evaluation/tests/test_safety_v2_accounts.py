"""ADR 0038: the safety_v2 runner signs in with each demo account's own password."""

from typing import Any

import pytest

from credassure.evaluation import safety_v2


class _Resp:
    def __init__(self, status: int, body: dict[str, Any]) -> None:
        self.status_code, self._body = status, body

    def json(self) -> dict[str, Any]:
        return self._body


class _Client:
    def __init__(self, own: dict[str, str], stage: str = "full") -> None:
        self.own, self.stage, self.seen = own, stage, []

    def post(self, url: str, json: dict[str, str]) -> _Resp:
        self.seen.append(json["username"])
        if self.own.get(json["username"]) != json["password"]:
            return _Resp(401, {})
        return _Resp(200, {"access_token": "t-" + json["username"], "stage": self.stage})


OWN = {
    "demo.preparer": "prep-own-pass-01",
    "demo.director": "dir-own-pass-002",
    "demo.evaluator": "eval-own-pass-03",
}


def test_ADR0038_runner_uses_each_accounts_own_password() -> None:
    runner = safety_v2.Runner(_Client(OWN), dict(OWN))  # type: ignore[arg-type]
    for who in ("preparer", "director", "evaluator"):
        assert runner.login(who) == {"Authorization": f"Bearer t-{safety_v2.USERS[who]}"}


def test_ADR0038_runner_explains_a_sign_in_it_cannot_finish() -> None:
    runner = safety_v2.Runner(_Client(OWN, stage="mfa"), dict(OWN))  # type: ignore[arg-type]
    with pytest.raises(RuntimeError, match="MFA_ENFORCED=false"):
        runner.login("director")


def test_ADR0038_run_names_the_missing_password_variables(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SEED_PASSWORD", "shared-pass-0001")  # not used any more
    for user in OWN:
        monkeypatch.delenv("SEED_PASSWORD_" + user.replace(".", "_").upper(), raising=False)
    with pytest.raises(SystemExit):
        safety_v2.main(["run", "--out", "unused.json"])
    err = capsys.readouterr().err
    assert "SEED_PASSWORD_DEMO_PREPARER" in err and "SEED_PASSWORD_DEMO_DIRECTOR" in err
    assert "shared-pass-0001" not in err
