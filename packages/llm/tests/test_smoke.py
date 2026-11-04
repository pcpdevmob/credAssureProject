"""Smoke test for credassure.llm."""

import credassure.llm


def test_smoke_import() -> None:
    assert credassure.llm is not None

    assert credassure.llm.sdk_name() == "openai"
