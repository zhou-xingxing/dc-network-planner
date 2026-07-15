"""add external access tokens and operation method

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-07-15 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "q8r9s0t1u2v3"
down_revision: Union[str, None] = "p7q8r9s0t1u2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_access_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_external_access_token_user", "external_access_tokens", ["user_id"])
    op.create_index("idx_external_access_token_expires", "external_access_tokens", ["expires_at"])
    op.create_index("ix_external_access_tokens_token_hash", "external_access_tokens", ["token_hash"], unique=True)

    with op.batch_alter_table("change_logs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("operation_method", sa.String(length=30), server_default="client", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("change_logs", schema=None) as batch_op:
        batch_op.drop_column("operation_method")

    op.drop_index("ix_external_access_tokens_token_hash", table_name="external_access_tokens")
    op.drop_index("idx_external_access_token_expires", table_name="external_access_tokens")
    op.drop_index("idx_external_access_token_user", table_name="external_access_tokens")
    op.drop_table("external_access_tokens")
