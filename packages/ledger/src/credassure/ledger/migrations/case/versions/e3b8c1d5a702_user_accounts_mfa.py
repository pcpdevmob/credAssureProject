"""users: account management, MFA and token revocation columns (ADR 0038)

Existing users keep working: no forced password change, MFA not enrolled, token_version 0.

Revision ID: e3b8c1d5a702
Revises: 7d2b9e4c1a30
Create Date: 2026-11-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3b8c1d5a702"
down_revision: str | None = "7d2b9e4c1a30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS: tuple[sa.Column[object], ...] = (
    sa.Column("display_name", sa.String(length=128), nullable=True),
    sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("mfa_secret", sa.Text(), nullable=True),
    sa.Column("mfa_last_step", sa.Integer(), nullable=True),
    sa.Column("mfa_backup", sa.JSON(), nullable=True),
    sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("created_at", sa.DateTime(), nullable=True),
    sa.Column("updated_at", sa.DateTime(), nullable=True),
)


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        for column in COLUMNS:
            batch.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        for column in reversed(COLUMNS):
            batch.drop_column(column.name)
