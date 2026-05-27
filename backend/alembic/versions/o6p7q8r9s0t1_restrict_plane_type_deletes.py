"""restrict network plane type deletes

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-05-27 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "o6p7q8r9s0t1"
down_revision: Union[str, None] = "n5o6p7q8r9s0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    with op.batch_alter_table("network_plane_types", schema=None) as batch_op:
        batch_op.drop_constraint("fk_network_plane_types_parent", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_network_plane_types_parent",
            "network_plane_types",
            ["parent_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table(
        "region_network_planes",
        schema=None,
        naming_convention=NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_region_network_planes_plane_type_id_network_plane_types",
            type_="foreignkey",
        )
        batch_op.create_foreign_key(
            "fk_region_network_planes_plane_type",
            "network_plane_types",
            ["plane_type_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("region_network_planes", schema=None) as batch_op:
        batch_op.drop_constraint("fk_region_network_planes_plane_type", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_region_network_planes_plane_type_id_network_plane_types",
            "network_plane_types",
            ["plane_type_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("network_plane_types", schema=None) as batch_op:
        batch_op.drop_constraint("fk_network_plane_types_parent", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_network_plane_types_parent",
            "network_plane_types",
            ["parent_id"],
            ["id"],
            ondelete="SET NULL",
        )
