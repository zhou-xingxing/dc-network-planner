"""扩展 IPv6 地址字段长度

Revision ID: f4c91b2a7d6e
Revises: ddd259908cce
Create Date: 2026-07-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4c91b2a7d6e"
down_revision: Union[str, None] = "ddd259908cce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """扩展字段以容纳最长 IPv4 嵌入式 IPv6 文本。"""
    with op.batch_alter_table("region_network_planes", schema=None) as batch_op:
        batch_op.alter_column(
            "cidr",
            existing_type=sa.String(length=43),
            type_=sa.String(length=49),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "gateway_ip",
            existing_type=sa.String(length=39),
            type_=sa.String(length=45),
            existing_nullable=True,
        )


def downgrade() -> None:
    """恢复原字段长度；已有超长值时降级可能失败。"""
    with op.batch_alter_table("region_network_planes", schema=None) as batch_op:
        batch_op.alter_column(
            "gateway_ip",
            existing_type=sa.String(length=45),
            type_=sa.String(length=39),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "cidr",
            existing_type=sa.String(length=49),
            type_=sa.String(length=43),
            existing_nullable=False,
        )
