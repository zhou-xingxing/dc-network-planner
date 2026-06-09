"""add change log entity name

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-06-09 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "p7q8r9s0t1u2"
down_revision: Union[str, None] = "o6p7q8r9s0t1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("change_logs", sa.Column("entity_name", sa.String(length=255), nullable=True))
    op.execute(
        """
        UPDATE change_logs
        SET entity_name = (
            SELECT regions.name
            FROM regions
            WHERE regions.id = change_logs.entity_id
        )
        WHERE entity_type = 'region' AND entity_name IS NULL
        """
    )
    op.execute(
        """
        UPDATE change_logs
        SET entity_name = (
            SELECT network_plane_types.name
            FROM network_plane_types
            WHERE network_plane_types.id = change_logs.entity_id
        )
        WHERE entity_type = 'network_plane_type' AND entity_name IS NULL
        """
    )
    op.execute(
        """
        UPDATE change_logs
        SET entity_name = (
            SELECT
                'Region=' || regions.name ||
                ', 网络平面=' || network_plane_types.name ||
                ', 作用域=' || region_network_planes.scope ||
                ', CIDR=' || region_network_planes.cidr ||
                CASE
                    WHEN region_network_planes.vlan_id IS NOT NULL
                    THEN ', VLAN=' || region_network_planes.vlan_id
                    ELSE ''
                END
            FROM region_network_planes
            JOIN regions ON regions.id = region_network_planes.region_id
            JOIN network_plane_types ON network_plane_types.id = region_network_planes.plane_type_id
            WHERE region_network_planes.id = change_logs.entity_id
        )
        WHERE entity_type = 'region_network_plane' AND entity_name IS NULL
        """
    )
    op.execute(
        """
        UPDATE change_logs
        SET entity_name = '备份配置'
        WHERE entity_type = 'backup_config' AND entity_name IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("change_logs", "entity_name")
