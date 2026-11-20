"""Test support for running the suite on MySQL (ADR 0039). Not used at runtime.

Set ``CREDASSURE_TEST_MYSQL_URL`` (for example ``mysql+pymysql://ca:pw@127.0.0.1/ca``; the user
needs CREATE and DROP on databases named ``<db>_*``) and the ledger and gateway fixtures give every
test its own MySQL database instead of a SQLite file. Unset, nothing changes.

Seeding 25 argon2 hashes and running every migration is slow, so a fixture builds one template
database per session and each test gets a copy: tables (with keys), rows and the append-only
triggers, in a fresh database.
"""

import itertools
import os
import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from .session import MYSQL_COLLATION

ENV = "CREDASSURE_TEST_MYSQL_URL"
DEFINER = re.compile(r"DEFINER=`[^`]*`@`[^`]*`\s*")
_count = itertools.count(1)
_run = uuid.uuid4().hex[:8]


def _literal(sql: str) -> str:
    """Copied DDL as a driver statement: pymysql formats `%`, so double it (CI's root@'%')."""
    return sql.replace("%", "%%")


def mysql_url() -> str | None:
    return os.environ.get(ENV) or None


def _name(url: str, label: str) -> str:
    base = make_url(url).database or "ca"
    return f"{base}_{_run}_{label}_{next(_count)}"


def _admin(url: str):  # type: ignore[no-untyped-def]  # an AUTOCOMMIT engine on the server
    server = make_url(url)._replace(database=None)  # URL.set() treats None as "unchanged"
    return create_engine(server, isolation_level="AUTOCOMMIT")


def create_database(url: str, label: str) -> str:
    """A new empty database; returns its URL (same server, user and options)."""
    name = _name(url, label)
    eng = _admin(url)
    with eng.connect() as c:
        c.exec_driver_sql(
            f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {MYSQL_COLLATION}"
        )
    eng.dispose()
    return make_url(url).set(database=name).render_as_string(hide_password=False)


def clone_database(url: str, template_url: str, label: str) -> str:
    """Copy the template's tables, rows and triggers into a new database; returns its URL."""
    target_url = create_database(url, label)
    source, target = make_url(template_url).database, make_url(target_url).database
    eng = _admin(url)
    with eng.connect() as c:
        c.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 0")
        c.exec_driver_sql(f"USE `{source}`")
        tables = [
            r[0] for r in c.exec_driver_sql("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
        ]
        ddl = [c.exec_driver_sql(f"SHOW CREATE TABLE `{t}`").one()[1] for t in tables]
        names = [r[0] for r in c.exec_driver_sql("SHOW TRIGGERS")]
        triggers = [c.exec_driver_sql(f"SHOW CREATE TRIGGER `{n}`").one()[2] for n in names]
        c.exec_driver_sql(f"USE `{target}`")
        for t, create in zip(tables, ddl, strict=True):
            c.exec_driver_sql(_literal(create))
            c.exec_driver_sql(f"INSERT INTO `{t}` SELECT * FROM `{source}`.`{t}`")  # noqa: S608  # nosec B608
        for create in triggers:  # without DEFINER=`user`@`%`: the copy runs as the current user
            c.exec_driver_sql(_literal(DEFINER.sub("", create)))
        c.exec_driver_sql("SET FOREIGN_KEY_CHECKS = 1")
    eng.dispose()
    return target_url


def drop_database(url: str) -> None:
    name = make_url(url).database
    eng = _admin(url)
    with eng.connect() as c:
        c.exec_driver_sql(f"DROP DATABASE IF EXISTS `{name}`")
    eng.dispose()


@contextmanager
def database(url: str, label: str) -> Iterator[str]:
    """A fresh database for one test, dropped afterwards."""
    db = create_database(url, label)
    try:
        yield db
    finally:
        drop_database(db)
