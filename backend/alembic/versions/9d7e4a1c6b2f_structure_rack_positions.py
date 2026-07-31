"""结构化机柜位置并清理旧机柜数据

Revision ID: 9d7e4a1c6b2f
Revises: 7b1d9e4c2a6f
Create Date: 2026-07-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d7e4a1c6b2f"
down_revision: Union[str, None] = "7b1d9e4c2a6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """清理无引用旧机柜，并增加严格的结构化位置约束。"""
    connection = op.get_bind()
    switch_count = connection.execute(sa.text("SELECT COUNT(*) FROM switches")).scalar_one()
    cable_count = connection.execute(sa.text("SELECT COUNT(*) FROM cable_entries")).scalar_one()
    if switch_count or cable_count:
        raise RuntimeError("旧机柜仍被交换机或线缆引用，不能执行结构化迁移")

    connection.execute(sa.text("DELETE FROM racks"))
    with op.batch_alter_table("racks", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("room_name", sa.String(length=100), nullable=False))
        batch_op.add_column(sa.Column("rack_column", sa.String(length=20), nullable=False))
        batch_op.add_column(sa.Column("rack_number", sa.Integer(), nullable=False))
        batch_op.create_check_constraint(
            "ck_rack_name_matches_parts",
            "name = room_name || '-' || rack_column || printf('%02d', rack_number)",
        )
        batch_op.create_check_constraint("ck_rack_number_positive", "rack_number > 0")
        batch_op.create_unique_constraint(
            "uq_rack_position",
            ["region_id", "room_name", "rack_column", "rack_number"],
        )


def downgrade() -> None:
    """移除结构化位置字段；已清理的旧机柜数据无法恢复。"""
    with op.batch_alter_table("racks", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_rack_position", type_="unique")
        batch_op.drop_constraint("ck_rack_number_positive", type_="check")
        batch_op.drop_constraint("ck_rack_name_matches_parts", type_="check")
        batch_op.drop_column("rack_number")
        batch_op.drop_column("rack_column")
        batch_op.drop_column("room_name")
