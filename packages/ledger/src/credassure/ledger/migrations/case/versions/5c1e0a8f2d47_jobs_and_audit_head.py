"""jobs (ADR 0007) and audit_head (OBJ-08 tail anchor)

Revision ID: 5c1e0a8f2d47
Revises: 37bd7037b99d
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c1e0a8f2d47"
down_revision: str | None = "37bd7037b99d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_head",
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id"),
    )
    # Anchor each tenant's existing tail so verification keeps passing after the upgrade.
    op.execute(
        "INSERT INTO audit_head (tenant_id, seq, hash) SELECT a.tenant_id, a.seq, a.hash "
        "FROM audit_log a WHERE a.seq = (SELECT max(b.seq) FROM audit_log b "
        "WHERE b.tenant_id = a.tenant_id)"
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "case_id", "idempotency_key"),
    )
    op.create_index("ix_jobs_tenant_id", "jobs", ["tenant_id"])
    op.create_index("ix_jobs_case_id", "jobs", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_case_id", table_name="jobs")
    op.drop_index("ix_jobs_tenant_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_table("audit_head")
