"""documents legal_basis and index_version (Phase 7)

Revision ID: b8582bd9a52e
Revises: a36d10db1598

Hand-written: autogenerate does not understand the FTS5 shadow tables and would drop them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8582bd9a52e"
down_revision: str | None = "a36d10db1598"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("legal_basis", sa.String(length=4), nullable=True))
        batch_op.add_column(sa.Column("index_version", sa.String(length=160), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_column("index_version")
        batch_op.drop_column("legal_basis")
