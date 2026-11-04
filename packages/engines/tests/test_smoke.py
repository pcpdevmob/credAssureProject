"""Smoke test for credassure.engines."""

import credassure.engines


def test_smoke_import() -> None:
    assert credassure.engines is not None
