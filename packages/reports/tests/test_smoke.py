"""Smoke test for credassure.reports."""

import credassure.reports


def test_smoke_import() -> None:
    assert credassure.reports is not None
