"""Ledger fixtures. ``case_target`` is a SQLite file, or a fresh MySQL database when
CREDASSURE_TEST_MYSQL_URL is set (ADR 0039), so the same tests run on both backends."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from credassure.ledger import testing


@pytest.fixture
def case_target(tmp_path: Path) -> Iterator[Path | str]:
    url = testing.mysql_url()
    if url is None:
        yield tmp_path / "case.db"
        return
    with testing.database(url, "ledger") as db:
        yield db
