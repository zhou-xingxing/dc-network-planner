from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.time_utils import utcnow_db

if TYPE_CHECKING:
    from app.models.network_plane_type import NetworkPlaneType
    from app.models.region import Region


def gen_uuid() -> str:
    return str(uuid.uuid4())


class RegionNetworkPlane(Base):
    __tablename__ = "region_network_planes"
    __table_args__ = (UniqueConstraint("region_id", "plane_type_id", "scope", name="uq_region_plane_type_scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    region_id: Mapped[str] = mapped_column(String(36), ForeignKey("regions.id", ondelete="CASCADE"))
    plane_type_id: Mapped[str] = mapped_column(String(36), ForeignKey("network_plane_types.id", ondelete="RESTRICT"))
    scope: Mapped[str] = mapped_column(String(100), nullable=False, default="Global")
    # IPv4/IPv6 CIDR 网络地址段，如 "10.0.0.0/22" 或 "2001:db8::/64"
    cidr: Mapped[str] = mapped_column(String(49), nullable=False)
    vlan_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    gateway_position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gateway_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_db)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_db, onupdate=utcnow_db)

    # relationships
    region: Mapped[Region] = relationship("Region", back_populates="region_planes")
    plane_type: Mapped[NetworkPlaneType] = relationship("NetworkPlaneType", back_populates="region_planes")
