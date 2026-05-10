"""add index for region network plane vlan id

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-05-10 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, None] = "l3m4n5o6p7q8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f("ix_region_network_planes_vlan_id"), "region_network_planes", ["vlan_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_region_network_planes_vlan_id"), table_name="region_network_planes")
