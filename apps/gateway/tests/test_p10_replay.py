"""P10 scope #17 (ADR 0015, NFR-08): the replay profile answers only from recorded replies."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from credassure.llm.cache import ResponseCache
from credassure.llm.client import OpenAICompatLLM


def test_NFR08_replay_needs_the_recorded_cache() -> None:
    from credassure.gateway.settings import Settings

    with pytest.raises(ValueError, match="REPLAY_MODE"):
        Settings(_env_file=None, app_env="test", replay_mode=True, llm_cache_path="")  # type: ignore[call-arg]


def test_NFR08_health_names_the_replay_profile(
    make_client: Callable[..., Any], tmp_path: Path
) -> None:
    client = make_client()
    llm = OpenAICompatLLM(
        "http://127.0.0.1:9/v1", None, "m", cache=ResponseCache(tmp_path / "c.db"), replay=True
    )
    client.app.state.services.llm = llm
    checks = client.get("/v1/health/ready").json()["checks"]
    assert checks["model"] == "replay"
