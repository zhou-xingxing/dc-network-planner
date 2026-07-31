"""将机柜位置唯一约束替换为普通复合索引

Revision ID: e7a3f1d5b9c2
Revises: c4b2e8f1a9d3
Create Date: 2026-07-31 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7a3f1d5b9c2"
down_revision: Union[str, None] = "c4b2e8f1a9d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _set_sqlite_foreign_keys(*, enabled: bool) -> None:
    """在重建被交换机和线缆引用的机柜表前后切换 SQLite 外键检查。"""
    if op.get_bind().dialect.name != "sqlite":
        return
    value = "ON" if enabled else "OFF"
    # SQLite 只能在事务外切换 foreign_keys，Alembic 的 autocommit block 会先结束当前事务。
    with op.get_context().autocommit_block():
        op.get_bind().exec_driver_sql(f"PRAGMA foreign_keys={value}")


def upgrade() -> None:
    """移除冗余位置唯一约束，保留同列查询和排序所需的普通索引。"""
    _set_sqlite_foreign_keys(enabled=False)
    try:
        with op.batch_alter_table("racks", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_rack_position", type_="unique")
            batch_op.create_index(
                "ix_rack_position",
                ["region_id", "room_name", "rack_column", "rack_number"],
                unique=False,
            )
    finally:
        _set_sqlite_foreign_keys(enabled=True)


def downgrade() -> None:
    """恢复机柜位置唯一约束。"""
    _set_sqlite_foreign_keys(enabled=False)
    try:
        with op.batch_alter_table("racks", recreate="always") as batch_op:
            batch_op.drop_index("ix_rack_position")
            batch_op.create_unique_constraint(
                "uq_rack_position",
                ["region_id", "room_name", "rack_column", "rack_number"],
            )
    finally:
        _set_sqlite_foreign_keys(enabled=True)
