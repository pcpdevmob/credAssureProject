"""drop offers, offer_evaluations, negotiation_messages (ADR 0023: the ledger is the record)

Refuses to run while any of the three tables holds a row: they were never written, so a row
means something unexpected and dropping it would lose data. The downgrade recreates them empty.

Revision ID: 7d2b9e4c1a30
Revises: 5c1e0a8f2d47
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7d2b9e4c1a30"
down_revision: str | None = "5c1e0a8f2d47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Children first: offer_evaluations references offers.
TABLES = ("offer_evaluations", "negotiation_messages", "offers")


class OfferTablesNotEmptyError(RuntimeError):
    pass


def upgrade() -> None:
    conn = op.get_bind()
    counts = {  # constant table names, no input
        t: conn.execute(sa.text(f"SELECT count(*) FROM {t}")).scalar_one()  # noqa: S608  # nosec B608
        for t in TABLES
    }
    if any(counts.values()):
        raise OfferTablesNotEmptyError(f"ADR 0023 drop refused, tables not empty: {counts}")
    for table in TABLES:
        op.drop_table(table)  # indexes go with the table


def downgrade() -> None:
    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=16), nullable=False),
        sa.Column("lender_id", sa.String(length=32), nullable=False),
        sa.Column("offer_id", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("kfs_doc_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id", "offer_id", "version"),
    )
    op.create_index("ix_offers_case_id", "offers", ["case_id"])
    op.create_index("ix_offers_tenant_id", "offers", ["tenant_id"])
    op.create_table(
        "negotiation_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=16), nullable=False),
        sa.Column("offer_id", sa.String(length=32), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("slots_json", sa.Text(), nullable=False),
        sa.Column("rendered_text", sa.Text(), nullable=False),
        sa.Column("critic_status", sa.String(length=16), nullable=True),
        sa.Column("response_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_negotiation_messages_case_id", "negotiation_messages", ["case_id"])
    op.create_index("ix_negotiation_messages_tenant_id", "negotiation_messages", ["tenant_id"])
    op.create_table(
        "offer_evaluations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("offer_row_id", sa.Integer(), nullable=False),
        sa.Column("comparable", sa.Boolean(), nullable=False),
        sa.Column("affordable", sa.Boolean(), nullable=True),
        sa.Column("amount_received_paise", sa.BigInteger(), nullable=True),
        sa.Column("total_repayment_paise", sa.BigInteger(), nullable=True),
        sa.Column("total_cost_paise", sa.BigInteger(), nullable=True),
        sa.Column("apr_text", sa.String(length=32), nullable=True),
        sa.Column("flags_json", sa.Text(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["offer_row_id"], ["offers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offer_evaluations_offer_row_id", "offer_evaluations", ["offer_row_id"])
    op.create_index("ix_offer_evaluations_tenant_id", "offer_evaluations", ["tenant_id"])
