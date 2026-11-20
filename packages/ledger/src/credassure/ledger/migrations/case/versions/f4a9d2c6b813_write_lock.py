"""write_lock: the one row every MySQL transaction locks first (ADR 0039)

SQLite never reads it (BEGIN IMMEDIATE already serialises writers); it is created on both so the
schema is the same whichever database holds case.db.

Revision ID: f4a9d2c6b813
Revises: e3b8c1d5a702
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4a9d2c6b813"
down_revision: str | None = "e3b8c1d5a702"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = op.create_table(
        "write_lock",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.bulk_insert(table, [{"id": 1}])


def downgrade() -> None:
    op.drop_table("write_lock")
