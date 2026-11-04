"""Smoke test for credassure.tools."""

import credassure.tools


def test_smoke_import() -> None:
    assert credassure.tools is not None
