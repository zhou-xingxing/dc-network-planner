from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, gen_uuid
from app.utils.time_utils import utcnow_db

if TYPE_CHECKING:
    from app.models.cabling import CablingBatch
    from app.models.rack import Rack
    from app.models.region_network_plane import RegionNetworkPlane
    from app.models.switch import SwitchGroup
    from app.models.user import UserRegionPermission


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_db)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_db, onupdate=utcnow_db)

    # relationships
    region_planes: Mapped[list[RegionNetworkPlane]] = relationship(
        "RegionNetworkPlane", back_populates="region", cascade="all, delete-orphan"
    )
    region_permissions: Mapped[list[UserRegionPermission]] = relationship(
        "UserRegionPermission", back_populates="region", cascade="all, delete-orphan"
    )
    racks: Mapped[list[Rack]] = relationship("Rack", back_populates="region", passive_deletes=True)
    switch_groups: Mapped[list[SwitchGroup]] = relationship(
        "SwitchGroup", back_populates="region", passive_deletes=True
    )
    cabling_batches: Mapped[list[CablingBatch]] = relationship(
        "CablingBatch", back_populates="region", passive_deletes=True
    )
