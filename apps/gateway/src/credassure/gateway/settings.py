"""Application settings, validated at startup (scope #30, NFR-07 fail closed).

Every variable in `.env.example` maps to one field here. Outside `APP_ENV=test`, a missing
`JWT_SECRET` (or `LLM_BASE_URL` while `LLM_ENABLED=true`) stops startup. Feature flags default
OFF; stretch items stay behind `FEATURE_STRETCH` (BRD §4.2).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, FilePath, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """All runtime configuration. Field names are the lower-case env variable names."""

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", frozen=True, hide_input_in_errors=True
    )

    app_env: Literal["dev", "test", "demo"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    tenant_id: str = "default"

    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    llm_context_tokens: int = Field(default=8192, gt=0)
    llm_supports_guided_json: bool = False
    llm_ca_cert: FilePath | None = None  # course CA file; must exist, empty = unset
    llm_max_tokens: int = Field(default=1024, gt=0, le=1024)  # course cap per call
    llm_disable_thinking: bool = False  # Qwen3: no <think> block (ADR 0017 amendment)
    # How thinking is turned off: Ollama /v1 honours reasoning_effort, vLLM chat_template_kwargs
    llm_thinking_switch: Literal["reasoning_effort", "chat_template_kwargs"] = (
        "chat_template_kwargs"
    )
    # ADR 0008 / scope #22, #23, #48: model-call resilience
    llm_call_timeout_s: float = Field(default=30.0, gt=0)
    stage_timeout_s: float = Field(default=300.0, gt=0)
    llm_max_retries: int = Field(default=2, ge=0, le=2)
    llm_circuit_failures: int = Field(default=5, gt=0)
    llm_circuit_open_s: float = Field(default=60.0, gt=0)
    llm_rate_per_minute: float = Field(default=60.0, gt=0)  # shared per team (NFR-04)
    llm_cache_path: str | None = "var/llm_cache.db"  # unset/empty turns the response cache off
    llm_enabled: bool = True
    embed_base_url: str | None = None
    embed_model: str | None = None
    reranker: Literal["none", "local_cross_encoder", "llm_pointwise"] = "none"
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_revision: str = "2cfc18c9415c912f9d8155881c133215df768a70"  # pinned (ADR 0013)
    # Plan v3.4 P4 (scope #62, #63): off until tuned on the retrieval dev split
    retrieval_query_rewrite: bool = False  # deterministic glossary expansion (config/glossary.yaml)
    answerability_threshold: float | None = None  # abstain when the top reranker score is lower
    rerank_order: bool = (
        True  # false = the reranker only scores for the gate (P4 ladder, user decision)
    )

    tracing_enabled: bool = True
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None

    case_db: Path = Path("var/case.db")
    hr_db: Path = Path("data/frozen/v1/hr.db")  # opened read-only (ONB-05)
    seed_password: SecretStr | None = None  # demo users only (make db); tests pass their own
    rate_limit: str = "120/minute"  # per user (JWT sub), else per client IP (NFR-04)
    token_quota: int = Field(default=2_000_000, gt=0)  # team quota; warnings at 70% / 90% (#16)
    max_upload_bytes: int = Field(default=2 * 1024 * 1024, gt=0)  # 2 MB (UI-02)

    jwt_secret: SecretStr | None = None
    jwt_expiry_minutes: int = Field(default=30, gt=0, le=30)
    ui_origins: str = "http://localhost:3000,http://localhost:5173"

    gst_rate: Decimal = Decimal("0.18")
    # S22 reference rates (R-RATE-02), loaded once at startup; engines never read the file.
    reference_rates_file: Path = Path("data/reference/reference_rates.yaml")
    lender_scripts_dir: Path = Path("data/frozen/v1/lender_scripts")  # S05, lender simulator
    corpus_db: Path = Path("var/corpus.db")  # Critic citation checks (VER-02), opened read-only
    corpus_manifest: Path = Path("data/corpus/manifest.yaml")  # superseded but unindexed docs
    # Copilot search (9e): the vector store and embedder are the ingest's (CHROMA_PATH, EMBED_*);
    # "keyword" runs BM25 only (tests, or no vector store).
    chroma_path: Path = Path("var/chroma")
    eval_dir: Path = Path("var/eval")  # P9 scorecards: `make eval` run folders (read-only)
    baseline_dir: Path = Path("evaluation/baseline/results")  # `make baseline` S1-S3 results
    copilot_search_mode: Literal["hybrid", "keyword"] = "hybrid"
    home_state: str = "IN-MH"  # ADR 0019 jurisdiction filter
    apr_convention: Literal["nominal", "effective"] = "nominal"
    boundary_rule: Literal["hold", "director", "vp"] = "hold"
    approval_threshold_paise: int = Field(default=1_500_000_000, gt=0)
    approval_step_up: bool = True  # NFR-07: approving above ₹1.5 crore re-checks the password
    forecast_weeks: int = Field(default=26, gt=0)
    agent_max_steps: int = Field(default=10, gt=0, le=10)
    token_cap_per_stage: int = Field(default=6000, gt=0)
    as_of_date: date = date(2026, 11, 15)
    credassure_seed: int = 20261026

    feature_stretch: bool = False
    planner_mode: Literal["fixed", "llm_proposes"] = "fixed"
    ablation: Literal["A1", "A2", "A3", "A4", "A5", "A6"] | None = None

    @field_validator("ablation", "llm_ca_cert", mode="before")
    @classmethod
    def _empty_is_unset(cls, value: object) -> object:
        return None if value == "" else value

    @model_validator(mode="after")
    def _fail_closed(self) -> Self:
        if self.app_env == "demo" and self.ablation == "A6":  # rails off never in a demo
            raise ValueError("ABLATION=A6 (guardrails off) is refused in the demo profile")
        if self.app_env == "test":
            return self
        problems: list[str] = []
        secret = self.jwt_secret.get_secret_value() if self.jwt_secret else ""
        if not secret:
            problems.append("JWT_SECRET is required")
        elif len(secret) < MIN_JWT_SECRET_LENGTH:
            problems.append(f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters")
        if self.llm_enabled and not self.llm_base_url:
            problems.append("LLM_BASE_URL is required when LLM_ENABLED=true")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def ui_origin_list(self) -> list[str]:
        return [o.strip() for o in self.ui_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings once per process from the environment and `.env`."""
    return Settings()
