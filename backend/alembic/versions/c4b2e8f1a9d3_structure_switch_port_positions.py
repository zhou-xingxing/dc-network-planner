"""结构化交换机物理端口位置

Revision ID: c4b2e8f1a9d3
Revises: 9d7e4a1c6b2f
Create Date: 2026-07-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4b2e8f1a9d3"
down_revision: Union[str, None] = "9d7e4a1c6b2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _set_sqlite_foreign_keys(*, enabled: bool) -> None:
    """在重建被线缆表引用的端口表前后切换 SQLite 外键检查。"""
    if op.get_bind().dialect.name != "sqlite":
        return
    value = "ON" if enabled else "OFF"
    # SQLite 只能在事务外切换 foreign_keys，Alembic 的 autocommit block 会先结束当前事务。
    with op.get_context().autocommit_block():
        op.get_bind().exec_driver_sql(f"PRAGMA foreign_keys={value}")


def upgrade() -> None:
    """增加板卡和子板卡坐标，并用完整物理位置保证端口唯一。"""
    _set_sqlite_foreign_keys(enabled=False)
    try:
        with op.batch_alter_table("switch_ports", recreate="always") as batch_op:
            batch_op.add_column(
                sa.Column("card_number", sa.Integer(), server_default="1", nullable=False)
            )
            batch_op.add_column(
                sa.Column("subcard_number", sa.Integer(), server_default="0", nullable=False)
            )
            batch_op.drop_constraint("uq_switch_port_number", type_="unique")
            batch_op.create_check_constraint(
                "ck_switch_port_card_number_nonnegative",
                "card_number >= 0",
            )
            batch_op.create_check_constraint(
                "ck_switch_port_subcard_number_nonnegative",
                "subcard_number >= 0",
            )
            batch_op.create_unique_constraint(
                "uq_switch_port_position",
                ["switch_id", "card_number", "subcard_number", "port_number"],
            )
    finally:
        _set_sqlite_foreign_keys(enabled=True)


def downgrade() -> None:
    """移除板卡层级；存在跨板卡同号端口时拒绝降级，避免数据丢失。"""
    duplicate = op.get_bind().execute(
        sa.text(
            "SELECT switch_id, port_number FROM switch_ports "
            "GROUP BY switch_id, port_number HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate:
        raise RuntimeError("存在跨板卡或子板卡的同号端口，不能移除结构化端口位置")

    _set_sqlite_foreign_keys(enabled=False)
    try:
        with op.batch_alter_table("switch_ports", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_switch_port_position", type_="unique")
            batch_op.drop_constraint("ck_switch_port_subcard_number_nonnegative", type_="check")
            batch_op.drop_constraint("ck_switch_port_card_number_nonnegative", type_="check")
            batch_op.create_unique_constraint(
                "uq_switch_port_number",
                ["switch_id", "port_number"],
            )
            batch_op.drop_column("subcard_number")
            batch_op.drop_column("card_number")
    finally:
        _set_sqlite_foreign_keys(enabled=True)
