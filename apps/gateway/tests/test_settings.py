"""Settings validation tests (scope #30, NFR-07 fail closed, APR-03 boundary rule)."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from credassure.gateway.settings import Settings

GOOD_SECRET = "x" * 40
MFA_KEY = "A" * 43 + "="  # base64 of 32 bytes (ADR 0038: required while MFA is enforced)
REPO_ROOT = Path(__file__).resolve().parents[3]


def make(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "dev",
        "llm_base_url": "https://llm.example.test/v1",
        "jwt_secret": GOOD_SECRET,
        "mfa_encryption_key": MFA_KEY,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def test_NFR07_settings_fail_closed_without_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        make(jwt_secret=None)


def test_NFR07_settings_fail_closed_without_llm_base_url_when_llm_enabled() -> None:
    with pytest.raises(ValidationError, match="LLM_BASE_URL"):
        make(llm_base_url=None)


def test_NFR07_settings_reject_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        make(jwt_secret="short")


def test_settings_llm_disabled_does_not_need_llm_base_url() -> None:
    s = make(llm_base_url=None, llm_enabled=False)
    assert s.llm_base_url is None


def test_settings_test_mode_allows_missing_secrets() -> None:
    s = Settings(_env_file=None, app_env="test")
    assert s.jwt_secret is None


def test_NFR07_secrets_not_in_repr() -> None:
    s = make(llm_api_key="sk-very-secret")
    assert GOOD_SECRET not in repr(s)
    assert "sk-very-secret" not in repr(s)


def test_APR03_boundary_rule_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        make(boundary_rule="auto_approve")


def test_APR03_boundary_rule_defaults_to_hold() -> None:
    assert make().boundary_rule == "hold"


def test_feature_flags_default_off() -> None:
    s = make()
    assert s.feature_stretch is False
    assert s.reranker == "none"
    assert s.planner_mode == "fixed"
    assert s.ablation is None


def test_money_settings_are_exact() -> None:
    s = make(gst_rate="0.18")
    assert isinstance(s.gst_rate, Decimal)
    assert s.gst_rate == Decimal("0.18")
    assert s.approval_threshold_paise == 1_50_00_000 * 100


def test_as_of_date_is_fixed_not_today() -> None:
    assert make().as_of_date == date(2026, 11, 15)


def test_NFR07_validation_errors_do_not_echo_secret_values() -> None:
    with pytest.raises(ValidationError) as err:
        make(jwt_secret="short-secret-value", llm_context_tokens="not-a-number")
    assert "short-secret-value" not in str(err.value)


def _replace_line(text: str, key: str, value: str) -> str:
    lines = [f"{key}={value}" if line.startswith(f"{key}=") else line for line in text.splitlines()]
    return "\n".join(lines) + "\n"


def test_env_example_loads_with_required_values_filled(tmp_path: Path) -> None:
    template = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    filled = _replace_line(template, "JWT_SECRET", GOOD_SECRET)
    filled = _replace_line(filled, "LLM_BASE_URL", "https://llm.example.test/v1")
    filled = _replace_line(filled, "MFA_ENCRYPTION_KEY", MFA_KEY)
    env_file = tmp_path / ".env"
    env_file.write_text(filled, encoding="utf-8")
    s = Settings(_env_file=env_file)
    assert s.llm_base_url == "https://llm.example.test/v1"
    assert s.llm_model == "qwen3:8b"
    assert s.llm_disable_thinking and s.llm_max_tokens == 1024 and s.llm_ca_cert is None
    assert s.embed_model == "nomic-embed-text"
    assert s.ablation is None
    assert s.boundary_rule == "hold"


@pytest.mark.parametrize("profile", ["local", "course"])
def test_NFR07_model_profiles_load_and_hold_no_secrets(profile: str) -> None:
    path = REPO_ROOT / "deploy" / "env" / f"models-{profile}.env"
    for line in path.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if line.startswith("#") or not sep:
            continue
        if name.endswith("_API_KEY"):
            assert value in ("", "ollama"), f"{name}: keys belong in the dotenv file only"
        if name.endswith("_CA_CERT"):
            assert value == "", "CA paths are machine-specific; profiles may only blank them"
    s = Settings(_env_file=path, jwt_secret=GOOD_SECRET, mfa_encryption_key=MFA_KEY)
    assert s.llm_disable_thinking and s.llm_max_tokens == 1024
    assert s.llm_model == {"local": "qwen3:8b", "course": "Qwen/Qwen3-8B"}[profile]
    # Ollama ignores chat_template_kwargs; only reasoning_effort turns Qwen3 thinking off there
    want = {"local": "reasoning_effort", "course": "chat_template_kwargs"}[profile]
    assert s.llm_thinking_switch == want
    if profile == "local":
        assert s.llm_ca_cert is None  # course CA in the dotenv file never reaches local mode


def test_NFR07_empty_ca_cert_is_unset_and_a_missing_file_fails_startup(tmp_path: Path) -> None:
    assert make(llm_ca_cert="").llm_ca_cert is None
    with pytest.raises(ValidationError, match="llm_ca_cert"):
        make(llm_ca_cert=str(tmp_path / "missing.crt"))
    ca = tmp_path / "vm06-ca.crt"
    ca.write_text("x", encoding="utf-8")
    assert make(llm_ca_cert=str(ca)).llm_ca_cert == ca


def test_scope30_every_setting_is_documented_and_in_env_example() -> None:
    """E17 SHOULD (Phase 10b item 11): Settings fields == the docs flag table == .env.example
    keys; the README feature flags are real settings."""
    import re
    from pathlib import Path

    from credassure.gateway.settings import Settings

    root = Path(__file__).resolve().parents[3]
    fields = {name.upper() for name in Settings.model_fields}
    doc = (root / "docs/setup/environment.md").read_text(encoding="utf-8")
    first_cells = re.findall(r"^\|([^|]*)\|", doc, re.M)
    documented = {n for cell in first_cells for n in re.findall(r"`([A-Z][A-Z0-9_]+)`", cell)}
    example = set(
        re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", (root / ".env.example").read_text(), re.M)
    )
    readme = (root / "README.md").read_text(encoding="utf-8")
    flags = readme.split("### Feature flags", 1)[1].split("\n\n>", 1)[0]
    readme_flags = set(re.findall(r"^\| `([A-Z][A-Z0-9_]+)`", flags, re.M))
    assert fields - documented == set()
    assert fields - example == set()
    assert readme_flags and readme_flags <= fields


def test_deploy_llm_fallback_is_unset_by_default_and_wraps_only_when_set() -> None:
    """Deployment plan §5.3: no fallback unless LLM_FALLBACK_BASE_URL is set; key kept secret."""
    from credassure.gateway.main import _default_llm
    from credassure.llm.client import OpenAICompatLLM
    from credassure.llm.failover import FailoverLLM

    base: dict[str, Any] = {
        "app_env": "test",
        "llm_base_url": "http://course.test/v1",
        "llm_cache_path": "",
    }
    plain = Settings(_env_file=None, **base, llm_fallback_base_url="")
    assert plain.llm_fallback_base_url is None
    assert isinstance(_default_llm(plain), OpenAICompatLLM)

    both = Settings(
        _env_file=None,
        **base,
        llm_model="Qwen/Qwen3-8B",
        llm_fallback_base_url="http://hf.test/v1",
        llm_fallback_api_key="hf-secret-token",
    )
    assert "hf-secret-token" not in repr(both)
    llm = _default_llm(both)
    assert isinstance(llm, FailoverLLM)
    assert (llm.primary.model, llm.fallback.model) == ("Qwen/Qwen3-8B", "Qwen/Qwen3-8B")
    assert llm.circuit_state == "closed"
    replay = Settings(
        _env_file=None,
        **{**base, "llm_cache_path": "var/x.db"},
        llm_fallback_base_url="http://hf.test/v1",
        replay_mode=True,
    )
    assert isinstance(_default_llm(replay), OpenAICompatLLM)  # replay never reaches an endpoint
