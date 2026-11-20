"""write_lock row and ledger_facts.source_ref as text (ADR 0039)

SQLite never reads it (BEGIN IMMEDIATE already serialises writers); it is created on both so the
schema is the same whichever database holds case.db. ledger_facts.source_ref becomes TEXT on MySQL:
SQLite never enforced VARCHAR(255), and a LendWise fact cites every offer and KFS file (1,500+
characters). SQLite is left alone: a batch ALTER would rebuild the table and drop its append-only
triggers, and SQLite stores the column as text either way.

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
    if op.get_bind().dialect.name != "mysql":
        return
    with op.batch_alter_table("ledger_facts") as batch:
        batch.alter_column(
            "source_ref", existing_type=sa.String(255), type_=sa.Text(), existing_nullable=False
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "mysql":
        op.drop_table("write_lock")
        return
    with op.batch_alter_table("ledger_facts") as batch:
        batch.alter_column(
            "source_ref", existing_type=sa.Text(), type_=sa.String(255), existing_nullable=False
        )
    op.drop_table("write_lock")
