"""Smoke test for credassure.ledger."""

import credassure.ledger


def test_smoke_import() -> None:
    assert credassure.ledger is not None
