"""新增交换机布线管理数据模型

Revision ID: 7b1d9e4c2a6f
Revises: f4c91b2a7d6e
Create Date: 2026-07-26 00:00:00.000000

"""

from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b1d9e4c2a6f"
down_revision: Union[str, None] = "f4c91b2a7d6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建布线资源、交换机组、布线批次和线缆条目表。"""
    op.create_table(
        "racks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("region_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("u_height", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("u_height > 0", name="ck_rack_u_height_positive"),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_rack_name"),
    )
    op.create_index(op.f("ix_racks_region_id"), "racks", ["region_id"], unique=False)

    switch_business_types = op.create_table(
        "switch_business_types",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_switch_business_type_code"),
        sa.UniqueConstraint("name", name="uq_switch_business_type_name"),
    )
    seeded_at = datetime.now(UTC).replace(tzinfo=None)
    op.bulk_insert(
        switch_business_types,
        [
            {
                "id": "10000000-0000-4000-8000-000000000001",
                "code": "business",
                "name": "业务",
                "created_at": seeded_at,
                "updated_at": seeded_at,
            },
            {
                "id": "10000000-0000-4000-8000-000000000002",
                "code": "management",
                "name": "管理",
                "created_at": seeded_at,
                "updated_at": seeded_at,
            },
            {
                "id": "10000000-0000-4000-8000-000000000003",
                "code": "storage",
                "name": "存储",
                "created_at": seeded_at,
                "updated_at": seeded_at,
            },
            {
                "id": "10000000-0000-4000-8000-000000000004",
                "code": "oob",
                "name": "带外",
                "created_at": seeded_at,
                "updated_at": seeded_at,
            },
        ],
    )

    op.create_table(
        "switch_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("region_id", sa.String(length=36), nullable=False),
        sa.Column("business_type_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("group_mode", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("group_mode IN ('pair', 'single')", name="ck_switch_group_mode"),
        sa.ForeignKeyConstraint(["business_type_id"], ["switch_business_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_switch_group_name"),
    )
    op.create_index(
        op.f("ix_switch_groups_business_type_id"),
        "switch_groups",
        ["business_type_id"],
        unique=False,
    )
    op.create_index(op.f("ix_switch_groups_region_id"), "switch_groups", ["region_id"], unique=False)

    op.create_table(
        "cabling_batches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("region_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["region_id"], ["regions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("region_id", "name", name="uq_cabling_batch_region_name"),
    )
    op.create_index(op.f("ix_cabling_batches_region_id"), "cabling_batches", ["region_id"], unique=False)

    op.create_table(
        "switches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rack_id", sa.String(length=36), nullable=False),
        sa.Column("switch_group_id", sa.String(length=36), nullable=True),
        sa.Column("member_role", sa.String(length=20), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("port_speed_mbps", sa.Integer(), nullable=False),
        sa.Column("start_u", sa.Integer(), nullable=False),
        sa.Column("height_u", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(switch_group_id IS NULL AND member_role IS NULL) OR "
            "(switch_group_id IS NOT NULL AND member_role IS NOT NULL)",
            name="ck_switch_group_member_pairing",
        ),
        sa.CheckConstraint("height_u > 0", name="ck_switch_height_u_positive"),
        sa.CheckConstraint(
            "member_role IS NULL OR member_role IN ('a', 'b', 'single')",
            name="ck_switch_member_role",
        ),
        sa.CheckConstraint("port_speed_mbps > 0", name="ck_switch_port_speed_mbps_positive"),
        sa.CheckConstraint("start_u > 0", name="ck_switch_start_u_positive"),
        sa.ForeignKeyConstraint(["rack_id"], ["racks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["switch_group_id"], ["switch_groups.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("switch_group_id", "member_role", name="uq_switch_group_member_role"),
        sa.UniqueConstraint("name", name="uq_switch_name"),
    )
    op.create_index(op.f("ix_switches_rack_id"), "switches", ["rack_id"], unique=False)
    op.create_index(op.f("ix_switches_switch_group_id"), "switches", ["switch_group_id"], unique=False)

    op.create_table(
        "switch_ports",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("switch_id", sa.String(length=36), nullable=False),
        sa.Column("port_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("port_number > 0", name="ck_switch_port_number_positive"),
        sa.ForeignKeyConstraint(["switch_id"], ["switches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("switch_id", "port_number", name="uq_switch_port_number"),
    )
    op.create_index(op.f("ix_switch_ports_switch_id"), "switch_ports", ["switch_id"], unique=False)

    op.create_table(
        "cable_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("server_rack_id", sa.String(length=36), nullable=False),
        sa.Column("server_start_u", sa.Integer(), nullable=False),
        sa.Column("server_height_u", sa.Integer(), nullable=False),
        sa.Column("server_port_name", sa.String(length=100), nullable=False),
        sa.Column("switch_port_id", sa.String(length=36), nullable=False),
        sa.Column("cable_label", sa.String(length=100), nullable=False),
        sa.Column("cable_sequence", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("cable_sequence > 0", name="ck_cable_entry_cable_sequence_positive"),
        sa.CheckConstraint("server_height_u > 0", name="ck_cable_entry_server_height_u_positive"),
        sa.CheckConstraint("server_start_u > 0", name="ck_cable_entry_server_start_u_positive"),
        sa.ForeignKeyConstraint(["batch_id"], ["cabling_batches.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["server_rack_id"], ["racks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["switch_port_id"], ["switch_ports.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cable_label", name="uq_cable_entry_cable_label"),
        sa.UniqueConstraint(
            "server_rack_id", "server_start_u", "server_port_name", name="uq_cable_entry_server_endpoint"
        ),
        sa.UniqueConstraint("switch_port_id", name="uq_cable_entry_switch_port"),
    )
    op.create_index(op.f("ix_cable_entries_batch_id"), "cable_entries", ["batch_id"], unique=False)
    op.create_index(op.f("ix_cable_entries_server_rack_id"), "cable_entries", ["server_rack_id"], unique=False)
    op.create_index(op.f("ix_cable_entries_switch_port_id"), "cable_entries", ["switch_port_id"], unique=False)


def downgrade() -> None:
    """删除交换机布线管理数据模型。"""
    op.drop_index(op.f("ix_cable_entries_switch_port_id"), table_name="cable_entries")
    op.drop_index(op.f("ix_cable_entries_server_rack_id"), table_name="cable_entries")
    op.drop_index(op.f("ix_cable_entries_batch_id"), table_name="cable_entries")
    op.drop_table("cable_entries")

    op.drop_index(op.f("ix_switch_ports_switch_id"), table_name="switch_ports")
    op.drop_table("switch_ports")

    op.drop_index(op.f("ix_switches_switch_group_id"), table_name="switches")
    op.drop_index(op.f("ix_switches_rack_id"), table_name="switches")
    op.drop_table("switches")

    op.drop_index(op.f("ix_cabling_batches_region_id"), table_name="cabling_batches")
    op.drop_table("cabling_batches")
    op.drop_index(op.f("ix_switch_groups_business_type_id"), table_name="switch_groups")
    op.drop_index(op.f("ix_switch_groups_region_id"), table_name="switch_groups")
    op.drop_table("switch_groups")
    op.drop_table("switch_business_types")
    op.drop_index(op.f("ix_racks_region_id"), table_name="racks")
    op.drop_table("racks")
