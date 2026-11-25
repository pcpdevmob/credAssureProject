"""ADR 0038 accounts through the gateway: `make db` / `make passwords` (credassure.gateway.seed).

Each account gets its own first password, written only to a 0600 hand-out file (never printed);
signing in with it reaches the password-change step, not the app.
"""

import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from credassure.gateway import seed as gateway_seed
from credassure.gateway.settings import Settings, get_settings


def _rows(path: Path) -> dict[str, tuple[str, str]]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            username, role, password = line.split()
            out[username] = (role, password)
    return out


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.chdir(tmp_path)  # no .env here
    for key in ("SEED_PASSWORD", "SEED_PASSWORD_DEMO_PREPARER", "CASE_DATABASE_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("CASE_DB", str(tmp_path / "var" / "case.db"))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def test_ADR0038_make_db_writes_one_own_password_per_account_never_prints_them(
    env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SEED_PASSWORD", "shared-pass-0001")  # an old .env: ignored, with a note
    assert gateway_seed.main([]) == 0
    handout = env / "var" / gateway_seed.HANDOUT
    rows = _rows(handout)
    assert len(rows) == 25 and len({p for _, p in rows.values()}) == 25
    assert rows["demo.vp"][0] == "vp_finance"
    assert stat.S_IMODE(handout.stat().st_mode) == 0o600
    out = capsys.readouterr()
    assert "SEED_PASSWORD is no longer used" in out.err
    assert not any(p in out.out + out.err for _, p in rows.values())
    assert "shared-pass-0001" not in out.out + out.err

    assert gateway_seed.main([]) == 0  # nothing new: the file is not appended to
    assert _rows(handout) == rows

    assert gateway_seed.main(["--reissue"]) == 0  # make passwords: new ones replace the file
    text = handout.read_text(encoding="utf-8")
    assert sum(line.startswith("# ") for line in text.splitlines()) == 3  # one batch only
    new = _rows(handout)  # one line per account: no older, no longer valid password left
    assert set(new) == set(rows) and all(new[u][1] != rows[u][1] for u in rows)
    assert stat.S_IMODE(handout.stat().st_mode) == 0o600


def test_ADR0038_first_password_leads_to_the_change_step_only(env: Path) -> None:
    from credassure.gateway.main import create_app

    assert gateway_seed.main([]) == 0
    rows = _rows(env / "var" / gateway_seed.HANDOUT)
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        jwt_secret="x" * 40,
        case_db=env / "var" / "case.db",
        llm_enabled=False,
        tracing_enabled=False,
    )
    with TestClient(create_app(settings)) as client:
        r = client.post(
            "/v1/auth/token",
            json={"username": "demo.preparer", "password": rows["demo.preparer"][1]},
        )
        assert r.status_code == 200
        assert r.json()["stage"] == "setup"  # must change it before using the app
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        assert client.get("/v1/cases", headers=h).status_code in (401, 403)
        other = client.post(
            "/v1/auth/token",
            json={"username": "demo.preparer", "password": rows["demo.vp"][1]},
        )
        assert other.status_code == 401  # another account's password does not work
