"""Settings validation tests (scope #30, NFR-07 fail closed, APR-03 boundary rule)."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from credassure.gateway.settings import Settings

GOOD_SECRET = "x" * 40
REPO_ROOT = Path(__file__).resolve().parents[3]


def make(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "app_env": "dev",
        "llm_base_url": "https://llm.example.test/v1",
        "jwt_secret": GOOD_SECRET,
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


def test_env_example_loads_with_required_values_filled(tmp_path: Path) -> None:
    template = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        template.replace("JWT_SECRET=", f"JWT_SECRET={GOOD_SECRET}").replace(
            "LLM_BASE_URL=", "LLM_BASE_URL=https://llm.example.test/v1"
        ),
        encoding="utf-8",
    )
    s = Settings(_env_file=env_file)
    assert s.ablation is None
    assert s.boundary_rule == "hold"
