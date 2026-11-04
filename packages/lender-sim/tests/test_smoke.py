"""Smoke test for credassure.lender_sim."""

import credassure.lender_sim


def test_smoke_import() -> None:
    assert credassure.lender_sim is not None
