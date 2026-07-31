from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, gen_uuid
from app.utils.time_utils import utcnow_db

if TYPE_CHECKING:
    from app.models.cabling import CableEntry
    from app.models.region import Region
    from app.models.switch import Switch


class Rack(Base):
    """Region 内用于定位交换机及服务器侧布线端点的机柜。"""

    __tablename__ = "racks"
    __table_args__ = (
        UniqueConstraint("name", name="uq_rack_name"),
        Index(
            "ix_rack_position",
            "region_id",
            "room_name",
            "rack_column",
            "rack_number",
        ),
        CheckConstraint("rack_number > 0", name="ck_rack_number_positive"),
        CheckConstraint(
            "name = room_name || '-' || rack_column || printf('%02d', rack_number)",
            name="ck_rack_name_matches_parts",
        ),
        CheckConstraint("u_height > 0", name="ck_rack_u_height_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    region_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("regions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rack_column: Mapped[str] = mapped_column(String(20), nullable=False)
    rack_number: Mapped[int] = mapped_column(Integer, nullable=False)
    u_height: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow_db, onupdate=utcnow_db)

    region: Mapped[Region] = relationship("Region", back_populates="racks")
    server_cable_entries: Mapped[list[CableEntry]] = relationship(
        "CableEntry", back_populates="server_rack", passive_deletes=True
    )
    switches: Mapped[list[Switch]] = relationship("Switch", back_populates="rack", passive_deletes=True)
