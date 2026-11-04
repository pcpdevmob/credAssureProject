"""Smoke test for credassure.security."""

import credassure.security


def test_smoke_import() -> None:
    assert credassure.security is not None
