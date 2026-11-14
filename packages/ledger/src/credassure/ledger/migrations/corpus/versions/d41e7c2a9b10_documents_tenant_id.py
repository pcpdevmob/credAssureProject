"""documents.tenant_id for case-scoped (KFS) documents (Phase 7, SUP-08)

Revision ID: d41e7c2a9b10
Revises: b8582bd9a52e
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d41e7c2a9b10"
down_revision: str | None = "b8582bd9a52e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tenant_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_column("tenant_id")
